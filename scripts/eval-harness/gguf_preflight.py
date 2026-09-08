#!/usr/bin/env python3
"""Écarte un candidat GGUF AVANT de télécharger plusieurs gigaoctets.

POURQUOI. Le 2026-09-08, `neutrino-8b-fv5.gguf` a coûté un cycle complet du
pipeline — 4,09 Go téléchargés, un redémarrage de LocalAI, un créneau de la file —
pour être rejeté au garde-fou d'appel d'outil avec :

    gguf_init_from_reader: tensor 'token_embd.weight' ...

Diagnostic : le fichier n'était NI tronqué (4 093 015 136 octets amont et local,
identiques) NI corrompu (magic `GGUF`, version 3, offsets tous dans les bornes).
Il déclarait simplement `general.file_type: 42` et 254 tenseurs de types **43 et
44**, alors que llama.cpp s'arrête à `GGML_TYPE_Q2_0 = 42` avec
`GGML_TYPE_COUNT = 43`. La carte du modèle l'assume : « The pack uses our FV5
tensor type, so it loads through our fork only ».

Or tout ça tient dans l'EN-TÊTE du fichier — 5,9 Mo sur 4,09 Go dans ce cas. Une
requête HTTP Range suffit donc à le savoir avant de payer le téléchargement.

CE QU'ON REFUSE (fail-closed, exit 3) : un type ggml ou un `file_type` au-delà de
ce que llama.cpp connaît. C'est une incompatibilité certaine, pas une supposition.

CE QU'ON LAISSE PASSER (fail-open, exit 0) : toute situation où on ne peut PAS
conclure — réseau indisponible, serveur sans support des requêtes Range, en-tête
illisible. Le pipeline normal reste juge. Bloquer sur une panne réseau ferait
manquer de bons candidats, ce qui est plus coûteux que de laisser filer un mauvais.

Usage :  gguf_preflight.py <url-ou-chemin>          # exit 0 = passe, 3 = écarté
         gguf_preflight.py <url> --verbose          # détaille l'en-tête
"""

from __future__ import annotations
import os
import struct
import sys
import urllib.request

# Relevé le 2026-09-08 dans ggml/include/ggml.h et include/llama.h de llama.cpp
# master. À rafraîchir quand l'amont ajoute des types (le message d'erreur nomme le
# numéro rencontré, donc un rejet à tort reste diagnosticable en une lecture).
# Surchargeable : GGUF_MAX_GGML_TYPE / GGUF_MAX_FTYPE.
MAX_GGML_TYPE = int(os.environ.get("GGUF_MAX_GGML_TYPE", "42"))  # GGML_TYPE_Q2_0
MAX_FTYPE = int(os.environ.get("GGUF_MAX_FTYPE", "41"))          # LLAMA_FTYPE_MOSTLY_Q2_0

NOMS_GGML = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0",
    9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K",
    15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S",
    20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16",
    26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16", 34: "TQ1_0",
    35: "TQ2_0", 39: "MXFP4", 40: "NVFP4", 41: "Q1_0", 42: "Q2_0",
}

FIXE = {0: ("B", 1), 1: ("b", 1), 2: ("H", 2), 3: ("h", 2), 4: ("I", 4),
        5: ("i", 4), 6: ("f", 4), 7: ("?", 1), 10: ("Q", 8), 11: ("q", 8),
        12: ("d", 8)}

BLOC = 1 << 20          # 1 Mio par requête Range
PLAFOND = 128 << 20     # au-delà, on renonce à lire l'en-tête (fail-open)


class PlusDeDonnees(Exception):
    """L'en-tête dépasse ce qu'on accepte de lire — on ne conclut pas."""


class Source:
    """Lecture séquentielle d'un GGUF distant (HTTP Range) ou local."""

    def __init__(self, cible: str):
        self.cible = cible
        self.local = not cible.startswith(("http://", "https://"))
        self.buf = b""
        self.pos = 0
        if self.local:
            self.buf = open(cible, "rb").read(PLAFOND)

    def _etendre(self, jusqua: int) -> None:
        if self.local or jusqua <= len(self.buf):
            return
        if jusqua > PLAFOND:
            raise PlusDeDonnees("en-tête au-delà de %d Mio" % (PLAFOND >> 20))
        fin = min(PLAFOND, ((jusqua // BLOC) + 1) * BLOC)
        req = urllib.request.Request(self.cible)
        req.add_header("Range", "bytes=%d-%d" % (len(self.buf), fin - 1))
        req.add_header("User-Agent", "gguf-preflight")
        with urllib.request.urlopen(req, timeout=30) as r:
            # 200 au lieu de 206 = le serveur ignore Range et renvoie tout : on
            # garde ce qu'il envoie jusqu'au plafond plutôt que d'avaler 4 Go.
            morceau = r.read(fin - len(self.buf)) if r.status == 206 else r.read(fin)
        if not morceau:
            raise PlusDeDonnees("le serveur n'a rien renvoyé pour la plage demandée")
        self.buf = self.buf + morceau if r.status == 206 else morceau

    def lire(self, n: int) -> bytes:
        self._etendre(self.pos + n)
        if self.pos + n > len(self.buf):
            raise PlusDeDonnees("fin de tampon atteinte")
        bloc = self.buf[self.pos:self.pos + n]
        self.pos += n
        return bloc

    def nb(self, fmt: str, n: int):
        return struct.unpack("<" + fmt, self.lire(n))[0]

    def chaine(self) -> str:
        return self.lire(self.nb("Q", 8)).decode("utf-8", "replace")


def valeur(s: Source, t: int):
    if t in FIXE:
        fmt, n = FIXE[t]
        return s.nb(fmt, n)
    if t == 8:
        return s.chaine()
    if t == 9:  # tableau
        ti = s.nb("I", 4)
        c = s.nb("Q", 8)
        for _ in range(c):
            valeur(s, ti)
        return "array[%d]" % c
    raise PlusDeDonnees("type de métadonnée inconnu: %r" % t)


def inspecte(cible: str) -> dict:
    s = Source(cible)
    if s.lire(4) != b"GGUF":
        return {"verdict": "REJET", "raison": "magic absent — ce n'est pas un GGUF"}
    version = s.nb("I", 4)
    n_tens = s.nb("Q", 8)
    n_kv = s.nb("Q", 8)

    kv = {}
    for _ in range(n_kv):
        cle = s.chaine()
        kv[cle] = valeur(s, s.nb("I", 4))

    types = {}
    for _ in range(n_tens):
        nom = s.chaine()
        nd = s.nb("I", 4)
        for _ in range(nd):
            s.nb("Q", 8)
        t = s.nb("I", 4)
        s.nb("Q", 8)  # offset
        types.setdefault(t, [0, nom])
        types[t][0] += 1

    info = {
        "version": version,
        "arch": kv.get("general.architecture"),
        "nom": kv.get("general.name"),
        "file_type": kv.get("general.file_type"),
        "nb_tenseurs": n_tens,
        "types": types,
        "octets_lus": s.pos,
    }

    inconnus = sorted(t for t in types if t > MAX_GGML_TYPE)
    if inconnus:
        det = ", ".join(
            "type %d (%d tenseurs, ex. %s)" % (t, types[t][0], types[t][1])
            for t in inconnus
        )
        info.update(
            verdict="REJET",
            raison="types de tenseurs inconnus de llama.cpp (max connu %d = %s) : %s"
                   % (MAX_GGML_TYPE, NOMS_GGML[MAX_GGML_TYPE], det),
        )
        return info

    ft = info["file_type"]
    if isinstance(ft, int) and ft > MAX_FTYPE:
        info.update(
            verdict="REJET",
            raison="general.file_type=%d au-delà du dernier llama_ftype connu (%d)"
                   % (ft, MAX_FTYPE),
        )
        return info

    info["verdict"] = "PASSE"
    return info


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verbose = "--verbose" in sys.argv
    if not args:
        print("usage: gguf_preflight.py <url-ou-chemin> [--verbose]", file=sys.stderr)
        return 2
    cible = args[0]

    try:
        info = inspecte(cible)
    except PlusDeDonnees as e:
        # Indéterminable : on ne bloque PAS. Cf. l'en-tête du fichier.
        print("preflight INDETERMINE (%s) — on laisse le pipeline juger" % e)
        return 0
    except Exception as e:  # noqa: BLE001 — fail-open volontaire, réseau compris
        print("preflight INDETERMINE (%r) — on laisse le pipeline juger" % e)
        return 0

    if verbose:
        print("  arch=%s  nom=%s  version=%s  file_type=%s  tenseurs=%s  en-tête=%d o"
              % (info.get("arch"), info.get("nom"), info.get("version"),
                 info.get("file_type"), info.get("nb_tenseurs"), info.get("octets_lus", 0)))
        for t, (c, ex) in sorted(info.get("types", {}).items()):
            print("    %-9s x%-4d  ex. %s" % (NOMS_GGML.get(t, "type?%d" % t), c, ex))

    if info["verdict"] == "REJET":
        print("preflight REJET : %s" % info["raison"])
        return 3
    print("preflight PASSE (arch=%s, file_type=%s, %d tenseurs)"
          % (info.get("arch"), info.get("file_type"), info.get("nb_tenseurs", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

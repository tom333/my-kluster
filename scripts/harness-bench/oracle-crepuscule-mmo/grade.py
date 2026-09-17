"""Correcteur CACHÉ de `crepuscule-mmo`. Déposé au moment de noter seulement.

Sept étages indépendants. Les deux premiers sont ceux du contrôle visible — ils
donnent le plancher « le serveur démarre et parle ». Les cinq autres sondent des
DÉCISIONS DE CONCEPTION, jamais des cas limites de calcul :

    autorite    le serveur croit-il le client sur parole ?
    tardif      un client qui arrive apprend-il ce qui existait déjà ?
    convergence deux clients voient-ils le même monde après des actions simultanées ?
    reconnexion l'identité est-elle portée par le jeton ou par la connexion ?
    reduction   le client web a-t-il une réduction d'état pure et testable ?

Une conception naïve — le serveur applique ce qu'on lui annonce et ne diffuse que
les changements — passe les deux premiers et échoue sur les quatre suivants. Ce
n'est pas un défaut d'implémentation, c'est un choix d'architecture qui ne se
rattrape pas après coup : c'est ce qui rend ce scénario utilisable pour mesurer
une phase de conception.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DELAI = 6.0


def _protocole(workdir):
    sys.path.insert(0, str(workdir))
    import protocole  # noqa: PLC0415 - dépend du workdir, donc importé tard

    return protocole


async def cas_connexion(p, workdir):
    async with p.Serveur(workdir) as s, p.Joueur(s.port, "a") as a:
        b = await a.entrer()
        if (b.get("x"), b.get("y")) != (0, 0):
            return "entree en (%s, %s) au lieu de (0, 0)" % (b.get("x"), b.get("y"))
        if not b.get("id"):
            return "pas d'identifiant dans `bienvenue`"
    return None


async def cas_propagation(p, workdir):
    """Le mouvement de l'un parvient à l'autre. Visible, donc facile."""
    async with p.Serveur(workdir) as s:
        async with p.Joueur(s.port, "a") as a, p.Joueur(s.port, "b") as b:
            await a.entrer()
            await b.entrer()
            depart = await b.etat_apres()
            await a.bouger(0, 1)
            vu = await b.etat_apres(depart["tick"])
            if [0, 1] not in (vu.get("joueurs") or {}).values():
                return "b ne voit pas a en (0,1) : %s" % (vu.get("joueurs"),)
    return None


async def cas_autorite(p, workdir):
    """Un bond de 9 cases. Le contrat dit « au plus une case par axe », et dit que
    la position reste INCHANGÉE — pas qu'elle est tronquée à la grille. Un serveur
    qui applique ce que le client annonce échoue ici, et lui seul."""
    async with p.Serveur(workdir) as s, p.Joueur(s.port, "a") as a:
        bienvenue = await a.entrer()
        depart = await a.etat_apres()
        await a.bouger(9, 9)
        await a.bouger(1, 0)  # un pas LÉGAL, pour avoir un repère après le triche
        vu = await a.etat_apres(depart["tick"])
        position = (vu.get("joueurs") or {}).get(bienvenue["id"])
        if position != [1, 0]:
            return "apres un bond de 9 puis un pas legal : %s, attendu [1, 0]" % (
                position,
            )
    return None


async def cas_tardif(p, workdir):
    """Le client tardif. Un serveur qui ne diffuse QUE les changements ne lui dira
    jamais que quelqu'un est déjà là — le joueur existant ne bouge plus."""
    async with p.Serveur(workdir) as s:
        async with p.Joueur(s.port, "ancien") as ancien:
            premier = await ancien.entrer()
            await ancien.bouger(1, 1)
            await ancien.etat_apres()
            async with p.Joueur(s.port, "nouveau") as nouveau:
                await nouveau.entrer()
                vu = await nouveau.etat_apres()
                joueurs = vu.get("joueurs") or {}
                if premier["id"] not in joueurs:
                    return "le tardif ignore le joueur deja present : %s" % (joueurs,)
                if joueurs[premier["id"]] != [1, 1]:
                    return "le tardif voit l'ancien en %s, attendu [1, 1]" % (
                        joueurs[premier["id"]],
                    )
    return None


async def cas_convergence(p, workdir):
    """Deux déplacements lancés sans attendre. Le contrat n'impose pas un ordre,
    il impose que les deux clients finissent sur le MÊME monde."""
    async with p.Serveur(workdir) as s:
        async with p.Joueur(s.port, "a") as a, p.Joueur(s.port, "b") as b:
            await a.entrer()
            await b.entrer()
            depart = max((await a.etat_apres())["tick"], (await b.etat_apres())["tick"])
            await asyncio.gather(a.bouger(1, 0), b.bouger(0, 1))
            vu_a = await a.etat_apres(depart + 1)
            vu_b = await b.etat_apres(vu_a["tick"] - 1)
            # Comparer des états de MÊME tick : sinon on punirait un décalage de
            # diffusion, qui n'est pas une divergence.
            while vu_b["tick"] < vu_a["tick"]:
                vu_b = await b.etat_apres(vu_b["tick"])
            while vu_a["tick"] < vu_b["tick"]:
                vu_a = await a.etat_apres(vu_a["tick"])
            if vu_a.get("joueurs") != vu_b.get("joueurs"):
                return "tick %s : a voit %s, b voit %s" % (
                    vu_a["tick"],
                    vu_a.get("joueurs"),
                    vu_b.get("joueurs"),
                )
    return None


async def cas_reconnexion(p, workdir):
    """L'identité est-elle portée par le jeton ou par la socket ?"""
    async with p.Serveur(workdir) as s:
        async with p.Joueur(s.port, "revenant") as premier:
            await premier.entrer()
            await premier.bouger(1, 1)
            await premier.etat_apres()
        async with p.Joueur(s.port, "revenant") as second:
            retour = await second.entrer()
            if (retour.get("x"), retour.get("y")) != (1, 1):
                return "retour en (%s, %s), attendu (1, 1)" % (
                    retour.get("x"),
                    retour.get("y"),
                )
    return None


PILOTE_JS = """
import { reduire } from '%s';
const depart = { tick: 0, joueurs: {} };
const a = reduire(depart, { type: 'etat', tick: 3, joueurs: { z: [2, 5] } });
const b = reduire(a, { type: 'inconnu' });
const c = reduire(a, { type: 'etat', tick: 4, joueurs: { z: [3, 5] } });
console.log(JSON.stringify({
  applique: a.tick === 3 && JSON.stringify(a.joueurs.z) === '[2,5]',
  inconnu_inerte: JSON.stringify(b) === JSON.stringify(a),
  pur: depart.tick === 0 && Object.keys(depart.joueurs).length === 0
       && a.tick === 3 && JSON.stringify(a.joueurs.z) === '[2,5]',
  suivant: c.tick === 4 && JSON.stringify(c.joueurs.z) === '[3,5]',
}));
"""


def cas_reduction(workdir):
    """Le client web, SANS navigateur. `crepuscule-amorce` a montré ce que coûte un
    étage qui exige un émulateur : il échoue en silence et ça ressemble à un défaut
    du modèle. Ici on teste la seule chose qui porte de la logique — la réduction
    d'état — et on la teste dans node."""
    module = Path(workdir) / "client" / "reduction.js"
    if not module.exists():
        return "client/reduction.js absent"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", dir=str(workdir), delete=False
    ) as f:
        f.write(PILOTE_JS % module.resolve().as_uri())
        pilote = f.name
    try:
        proc = subprocess.run(
            ["node", pilote], capture_output=True, text=True, timeout=60
        )
    finally:
        Path(pilote).unlink(missing_ok=True)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout).strip().splitlines()[-1][:200]
    try:
        verdicts = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "sortie node illisible : %s" % proc.stdout.strip()[:150]
    rates = [nom for nom, ok in verdicts.items() if not ok]
    return ("echoue : " + ", ".join(rates)) if rates else None


CAS_RESEAU = (
    ("connexion", cas_connexion),
    ("propagation", cas_propagation),
    ("autorite", cas_autorite),
    ("tardif", cas_tardif),
    ("convergence", cas_convergence),
    ("reconnexion", cas_reconnexion),
)


async def joue_reseau(workdir):
    p = _protocole(workdir)
    resultats = {}
    for nom, fonction in CAS_RESEAU:
        try:
            detail = await asyncio.wait_for(fonction(p, workdir), 90)
        except Exception as exc:  # noqa: BLE001 - un cas qui plante est un cas rate
            detail = "%s: %s" % (type(exc).__name__, str(exc)[:200])
        resultats[nom] = {"ok": detail is None, "detail": detail or ""}
    return resultats


def main(workdir):
    workdir = Path(workdir).resolve()
    if not (workdir / "serveur.py").exists():
        resultats = {
            nom: {"ok": False, "detail": "serveur.py absent"} for nom, _ in CAS_RESEAU
        }
    else:
        resultats = asyncio.run(joue_reseau(workdir))
    detail = cas_reduction(workdir)
    resultats["reduction"] = {"ok": detail is None, "detail": detail or ""}
    print(json.dumps(resultats, ensure_ascii=False))
    return 0 if all(r["ok"] for r in resultats.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))

"""Offres d'emploi tech / data / IA en Nouvelle-Calédonie (porté du flux Kestra `emploi-nc`).

Pages HTML lues en texte, ou par un lecteur dédié (API JSON / page à trier), extraction par le
LLM page par page en JSON strict, filtre tech/data, dédup par empreinte titre+entreprise
(état : /data/etat/emploi_nc_vues.json), message Telegram. Une source en erreur est signalée
dans le message, pas en échec du job.
"""

import hashlib
import json
import os
import re
import urllib.request
from html import unescape

import commun

UA = commun.UA


def texte_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr"})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read(600_000).decode("utf-8", "replace")
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    # garder les liens : « texte (href) » pour que le LLM rende de vrais href
    html = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: " %s (%s) " % (re.sub(r"<[^>]+>", " ", m.group(2)), m.group(1)), html)
    t = " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())
    return t[:9000]

def lignes_lemploi(base):
    # Appli Inertia.js : chaque page HTML porte sa liste d'offres en JSON dans
    # l'attribut `data-page` (pas besoin de la poignée de main X-Inertia-Version).
    # 12 offres par page, `?page=N`, lien de détail = /offres-d-emploi/{slug}.
    lignes, page, derniere = [], 1, 1
    while page <= min(derniere, 20):
        req = urllib.request.Request("%s?page=%d" % (base, page), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", "replace")
        m = re.search(r'data-page="([^"]+)"', h)
        if not m:
            break
        j = json.loads(unescape(m.group(1)))["props"]["jobOffers"]
        derniere = j.get("last_page") or 1
        for o in j.get("data", []):
            lignes.append("%s | %s | %s | %s | %s (https://www.lemploi.nc/offres-d-emploi/%s)" % (
                o.get("title"), o.get("company"), o.get("city"),
                o.get("jobFunctions"), o.get("areaActivities"), o.get("slug")))
        page += 1
    return lignes

# Le site carrières de la CPS est une marque blanche TR1 : le navigateur charge les
# offres depuis cette API (URL relevée dans l'onglet Réseau, 2026-10-28).
SPC_API = ("https://api.tr1.com.au/backend/public/api/getjoblist/369010d0-d94b-4783-8f0f-ff7f92563f59"
           "?domainWithHttp=https://fr.careers.spc.int&sort=newest&perPage=50&page=%d")

def lignes_spc(base):
    lignes, page = [], 1
    while page <= 10:
        req = urllib.request.Request(SPC_API % page, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as r:
            j = json.load(r)["data"]["jobs"]
        items = j.get("items") or []
        for o in items:
            lignes.append("%s | Communauté du Pacifique (CPS) | %s | %s (https://fr.careers.spc.int/view/%s)" % (
                o.get("title"), (o.get("location") or {}).get("location"),
                " ".join((o.get("description") or "").split())[:200], o.get("id")))
        if not items or len(lignes) >= (j.get("totalRecord") or 0):
            break
        page += 1
    return lignes

def lignes_hellowork(base):
    # Une carte d'offre = un bloc `data-cy="serpCard"`. Seules les offres OUVERTES ont un
    # lien /fr-fr/emplois/<id>.html ; les expirées (« n'est plus disponible ») n'en ont pas.
    req = urllib.request.Request(base, headers={"User-Agent": UA, "Accept-Language": "fr"})
    with urllib.request.urlopen(req, timeout=40) as r:
        h = r.read(2_000_000).decode("utf-8", "replace")
    debuts = [m.start() for m in re.finditer(r'data-cy="serpCard"', h)] + [len(h)]
    lignes = []
    for a, b in zip(debuts, debuts[1:]):
        bloc = h[a:b]
        lien = re.search(r'href="(/fr-fr/emplois/\d+\.html)', bloc)
        if not lien:
            continue
        bloc = re.sub(r"(?is)<(script|style|svg|button)[^>]*>.*?</\1>", " ", bloc)
        texte = " ".join(unescape(re.sub(r"<[^>]+>", " ", bloc)).split())
        texte = texte.replace('data-cy="serpCard" >', "").split("Voir l’offre")[0].strip()
        lignes.append("%s (https://www.hellowork.com%s)" % (texte[:300], lien.group(1)))
    return lignes

# Sources à lecteur dédié (API JSON ou page à trier) : une liste vide y est légitime
# (aucune offre ouverte), pas une erreur.
SOURCES_JSON = {"lemploi.nc/offres-d-emploi": lignes_lemploi, "careers.spc.int": lignes_spc,
                "hellowork.com/fr-fr/entreprises/": lignes_hellowork}

def llm(page, texte):
    consigne = (
        "Tu extrais des OFFRES D'EMPLOI depuis le texte d'une page web (les liens y figurent entre "
        "parenthèses après leur libellé). Ne garde QUE les offres tech / data / IT : data (analyst, "
        "scientist, engineer), machine learning / IA, développement, Python, SQL, DevOps, réseau, "
        "cybersécurité. Jette tout le reste (mécanique, vente, secrétariat, santé, finance non-IT…). "
        "Réponds UNIQUEMENT par un tableau JSON, sans texte autour : "
        '[{"titre": "...", "entreprise": "...", "lieu": "...", "lien": "..."}]. '
        "Le lien est l'URL entre parenthèses la plus proche du titre ; si elle est relative, "
        "préfixe-la par l'origine de la page ; s'il n'y en a pas, mets l'URL de la page. "
        "Aucune offre : []."
    )
    contenu = commun.llm(consigne, "PAGE: %s\n\n%s" % (page, texte), max_tokens=1500, temperature=0.2) or "[]"
    m = re.search(r"\[.*\]", contenu, re.S)
    try:
        return json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []


def main():
    pages = json.load(open(os.path.join(commun.CODE, "emploi_pages.json"), encoding="utf-8"))
    vues = set(commun.lire_etat("emploi_nc_vues", []))
    offres, erreurs, nouvelles = [], [], []
    for page in pages:
        lecteur = next((f for motif, f in SOURCES_JSON.items() if motif in page), None)
        try:
            if lecteur:
                ls = lecteur(page)
                # ~100 offres possibles : paquets de 40 lignes (~8 000 car.) pour rester court par appel
                morceaux = ["\n".join(ls[i:i + 40]) for i in range(0, len(ls), 40)]
            else:
                morceaux = [texte_page(page)]
        except Exception as e:
            erreurs.append("%s : %s" % (page, str(e)[:60]))
            continue
        if not lecteur and len(morceaux[0]) < 200:
            erreurs.append("%s : page vide (%d car.)" % (page, len(morceaux[0])))
            continue
        for o in (x for t in morceaux for x in llm(page, t)):
            if not isinstance(o, dict) or not o.get("titre"):
                continue
            cle = hashlib.sha1(("%s|%s" % (o.get("titre", ""), o.get("entreprise", ""))).lower().encode()).hexdigest()[:16]
            offres.append(cle)
            if cle not in vues:
                nouvelles.append(o)
    print("  %d offre(s) tech retenue(s), %d nouvelle(s), %d source(s) en erreur" % (len(offres), len(nouvelles), len(erreurs)), flush=True)
    lignes = ["• %s — %s (%s) — %s" % (o.get("titre", "?"), o.get("entreprise", "?"), o.get("lieu", "NC"), o.get("lien", "")) for o in nouvelles]
    texte = "💼 Offres tech/data NC — %d nouvelle(s)\n\n" % len(nouvelles) + "\n".join(lignes) if nouvelles else ""
    if erreurs:
        texte += ("\n\n" if texte else "⚠️ Emploi NC — aucune nouvelle offre, mais des sources en erreur :\n") + "\n".join("⚠️ " + e for e in erreurs)
    if texte:
        commun.telegram(texte)
    # mémoire bornée : les 2 000 dernières empreintes vues
    commun.ecrire_etat("emploi_nc_vues", (list(vues) + [c for c in offres if c not in vues])[-2000:])


if __name__ == "__main__":
    commun.principal("emploi-nc", main)

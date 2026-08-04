"""ÉTAGE 11 — rendu HTML.

`colonnes.web.rendu_html(jeu)` rend une page HTML complète et DÉTERMINISTE
représentant l'état du jeu.

- Document complet : commence par `<!DOCTYPE html>`, contient `<html` et `</html>`.
- Une `<table id="plateau">` de `hauteur` lignes `<tr>` et `largeur` cellules `<td>`
  par ligne, de la ligne 0 vers le bas.
- Une case vide s'écrit `<td class="vide"></td>`.
- Une case occupée par la tuile `X` s'écrit `<td class="tuile-X">X</td>`.
- Les trois tuiles de la colonne EN CHUTE apparaissent aussi, avec la classe
  supplémentaire `chute` : `<td class="tuile-X chute">X</td>`. Elles ne sont pas
  posées sur le `Plateau`, mais le joueur doit les voir : chacune OCCUPE SA CASE
  DANS LE TABLEAU, à la ligne `jeu.ligne + i` et la colonne `jeu.col`, et REMPLACE
  la cellule qui s'y trouverait. Le tableau garde donc exactement
  `hauteur * largeur` cellules, jamais trois de plus.
- Le score apparaît dans `<span id="score">…</span>`.
- Quand la partie est terminée, la page contient `<p id="fin">Partie terminée</p>`
  et ne le contient pas sinon.
"""

import re

from colonnes import Jeu
from colonnes.web import rendu_html


def cellules(html):
    """Les `<td …>…</td>` dans l'ordre du document."""
    return re.findall(r"<td[^>]*>.*?</td>", html, re.S)


def test_document_complet():
    html = rendu_html(Jeu(iter(["ABC"]), largeur=4, hauteur=3))
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<html" in html and "</html>" in html


def test_table_aux_dimensions_du_plateau():
    html = rendu_html(Jeu(iter(["ABC"]), largeur=4, hauteur=6))
    assert '<table id="plateau"' in html
    assert len(re.findall(r"<tr[^>]*>", html)) == 6
    assert len(cellules(html)) == 24


def test_case_vide():
    html = rendu_html(Jeu(iter([]), largeur=3, hauteur=3))
    assert cellules(html) == ['<td class="vide"></td>'] * 9


def test_case_occupee():
    j = Jeu(iter([]), largeur=3, hauteur=3)
    j.plateau.poser(2, 1, "D")
    html = rendu_html(j)
    assert '<td class="tuile-D">D</td>' in html
    assert cellules(html)[7] == '<td class="tuile-D">D</td>'


def test_colonne_en_chute_visible_et_marquee():
    j = Jeu(iter(["ABC"]), largeur=3, hauteur=6)
    html = rendu_html(j)
    # apparition en (0,1), (1,1), (2,1) puisque largeur // 2 == 1
    assert '<td class="tuile-A chute">A</td>' in html
    assert '<td class="tuile-B chute">B</td>' in html
    assert '<td class="tuile-C chute">C</td>' in html


def test_la_chute_n_est_pas_sur_le_plateau():
    """Le plateau lui-même reste vide : la marque `chute` est la seule différence."""
    j = Jeu(iter(["ABC"]), largeur=3, hauteur=6)
    assert j.plateau.rendu() == "\n".join(["..."] * 6)
    assert rendu_html(j).count("chute") == 3


def test_score_affiche():
    j = Jeu(iter(["XYA", "DEF"]), largeur=4, hauteur=6)
    j.plateau.poser(5, 1, "A")
    j.plateau.poser(5, 3, "A")
    j.chuter()
    assert j.score == 30
    assert re.search(r'<span id="score">\s*30\s*</span>', rendu_html(j))


def test_fin_de_partie_annoncee():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert '<p id="fin">' not in rendu_html(j)
    j.chuter()
    assert j.partie_terminee is True
    assert '<p id="fin">Partie terminée</p>' in rendu_html(j)


def test_rendu_deterministe():
    j = Jeu(iter(["ABC"]), largeur=4, hauteur=6)
    assert rendu_html(j) == rendu_html(j)

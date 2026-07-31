"""Contrat d'EXTENSION — rendu texte et boucle d'entrées.

Le paquet `tetris` existe déjà et ses 44 tests passent : ne le casse pas. Ajoute
deux fonctions publiques, exportées par le paquet `tetris` :

    from tetris import rendu, boucle

`rendu(game) -> str` — fonction PURE (elle ne modifie rien) qui rend l'état du
jeu en texte, exactement ainsi :

- `game.height` lignes de `game.width` caractères, de la ligne 0 (en haut) vers
  le bas, séparées par `"\\n"` ;
- un caractère par case : `'#'` si la case est verrouillée dans le plateau,
  sinon `'@'` si elle est occupée par la pièce active, sinon `'.'` ;
- la pièce active n'est PAS dessinée quand `game.game_over` est vrai ;
- puis une ligne exactement `"score:S niveau:N lignes:L"` avec les valeurs de
  `game.score`, `game.level` et `game.lines_cleared` ;
- puis, SEULEMENT si `game.game_over`, une dernière ligne `"perdu"` ;
- aucun saut de ligne final.

`boucle(game, entrees) -> Game` — applique les entrées dans l'ordre et rend le
jeu (le MÊME objet, pas une copie) :

- `"gauche"` → `game.move(-1)` ; `"droite"` → `game.move(1)` ;
- `"rot"` → `game.rotate(1)` ; `"chute"` → `game.hard_drop()` ;
- dès que `game.game_over` est vrai, les entrées restantes sont ignorées ;
- toute autre entrée lève `ValueError`.

Indice : la matrice d'une pièce tournée ne contient pas de `'.'` (voir
`Piece._get_matrix`). Passe par `piece.cells()` ou `game.cells()`, jamais par
`piece.matrix`.
"""

import pytest

from tetris import Game, boucle, rendu


# --- rendu -----------------------------------------------------------------


def test_rendu_petit_plateau_piece_o():
    assert rendu(Game(iter(["O"]), width=4, height=3)) == (
        ".@@.\n.@@.\n....\nscore:0 niveau:1 lignes:0"
    )


def test_rendu_piece_t_centree():
    assert rendu(Game(iter(["T"]), width=5, height=4)) == (
        "..@..\n.@@@.\n.....\n.....\nscore:0 niveau:1 lignes:0"
    )


def test_rendu_distingue_verrouille_et_actif():
    game = Game(iter(["O", "O"]), width=4, height=3)
    game.board.place({(2, 0), (2, 3)})
    assert rendu(game) == ".@@.\n.@@.\n#..#\nscore:0 niveau:1 lignes:0"


def test_rendu_apres_une_chute():
    game = Game(iter(["O", "T"]), width=4, height=4)
    game.hard_drop()
    assert rendu(game) == ".@..\n@@@.\n.##.\n.##.\nscore:4 niveau:1 lignes:0"


def test_rendu_partie_perdue():
    game = Game(iter(["O"]), width=4, height=3)
    game.hard_drop()  # plus aucune pièce à suivre
    assert game.game_over
    assert rendu(game) == "....\n.##.\n.##.\nscore:2 niveau:1 lignes:0\nperdu"


def test_rendu_pas_de_piece_active_si_perdu():
    game = Game(iter(["O"]), width=4, height=3)
    game.hard_drop()
    assert "@" not in rendu(game)


def test_rendu_respecte_les_dimensions_par_defaut():
    lignes = rendu(Game(iter(["O"]))).split("\n")
    assert len(lignes) == 21  # 20 lignes de plateau + la ligne de score
    assert all(len(ligne) == 10 for ligne in lignes[:20])
    assert lignes[0] == "....@@...."


def test_rendu_sans_saut_de_ligne_final():
    texte = rendu(Game(iter(["O"]), width=4, height=3))
    assert not texte.endswith("\n")


def test_rendu_suit_le_score():
    game = Game(iter(["O"]), width=4, height=6)
    game.soft_drop()
    assert rendu(game).splitlines()[-1] == "score:1 niveau:1 lignes:0"


def test_rendu_est_pur():
    game = Game(iter(["T"]), width=5, height=4)
    avant = (game.row, game.col, game.score, game.piece.rotation)
    premier = rendu(game)
    second = rendu(game)
    assert premier == second
    assert (game.row, game.col, game.score, game.piece.rotation) == avant


# --- boucle ----------------------------------------------------------------


def test_boucle_gauche():
    game = Game(iter(["O"]), width=4, height=3)
    col = game.col
    boucle(game, ["gauche"])
    assert game.col == col - 1


def test_boucle_droite():
    game = Game(iter(["O"]), width=6, height=3)
    col = game.col
    boucle(game, ["droite"])
    assert game.col == col + 1


def test_boucle_rot():
    game = Game(iter(["T"]), width=5, height=4)
    boucle(game, ["rot"])
    assert game.piece.rotation == 1


def test_boucle_chute_verrouille_et_enchaine():
    game = Game(iter(["O", "T"]), width=4, height=4)
    boucle(game, ["chute"])
    assert game.piece.name == "T"
    assert game.board.occupied(3, 1)
    assert game.score == 4


def test_boucle_applique_dans_l_ordre():
    game = Game(iter(["O"]), width=6, height=3)
    boucle(game, ["gauche", "gauche", "droite"])
    assert game.col == 1


def test_boucle_ignore_les_entrees_apres_la_fin():
    game = Game(iter(["O"]), width=4, height=3)
    boucle(game, ["chute", "gauche", "rot"])
    assert game.game_over
    assert rendu(game).endswith("perdu")


def test_boucle_entree_inconnue():
    game = Game(iter(["O"]), width=4, height=3)
    with pytest.raises(ValueError):
        boucle(game, ["haut"])


def test_boucle_rend_le_meme_objet():
    game = Game(iter(["O"]), width=4, height=3)
    assert boucle(game, []) is game

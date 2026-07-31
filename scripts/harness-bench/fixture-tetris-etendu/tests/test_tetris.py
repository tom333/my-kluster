"""Spécification exécutable d'un Tetris déterministe. NE PAS MODIFIER.

Ce fichier EST le contrat. Le paquet `tetris/` n'existe pas encore : il doit être
écrit pour satisfaire ces tests.

CONTRAT PUBLIC ATTENDU
======================

    from tetris import SHAPES, Piece, Board, Bag, Game

Repère : `row` croît vers le BAS, `col` croît vers la DROITE. Une cellule est un
couple `(row, col)`. Plateau par défaut : 10 colonnes × 20 lignes.

--- tetris.SHAPES ---
Dict `nom -> liste de chaînes`, la matrice carrée de la pièce en rotation 0.
'#' = plein, '.' = vide. Ces sept matrices sont imposées telles quelles :

    "I": ["....", "####", "....", "...."]      (4x4)
    "O": ["##", "##"]                          (2x2)
    "T": [".#.", "###", "..."]                 (3x3)
    "S": [".##", "##.", "..."]                 (3x3)
    "Z": ["##.", ".##", "..."]                 (3x3)
    "J": ["#..", "###", "..."]                 (3x3)
    "L": ["..#", "###", "..."]                 (3x3)

--- tetris.Piece ---
    Piece(name, rotation=0)
    .name                 str
    .rotation             int, toujours ramené dans 0..3
    .size                 int, côté de la matrice
    .cells()              frozenset des (row, col) pleines, RELATIVES à la matrice
    .rotated(turns)       nouvelle Piece, +turns quarts de tour horaires
La rotation horaire d'une matrice carrée : la colonne 0 lue de bas en haut devient
la ligne 0. `rotation` est cyclique modulo 4, y compris pour les valeurs négatives.

--- tetris.Board ---
    Board(width=10, height=20)
    .width .height
    .is_inside(row, col)  -> bool
    .is_free(cells)       -> bool ; vrai si TOUTES les cellules sont dans le plateau
                             ET libres
    .place(cells)         -> None ; marque les cellules occupées
    .occupied(row, col)   -> bool
    .clear_lines()        -> int ; retire les lignes pleines, fait descendre ce qui
                             est au-dessus, retourne le nombre de lignes retirées
    .full_rows()          -> liste triée des indices de lignes pleines

--- tetris.Bag ---
    Bag(seed)
    .__next__()           -> nom de pièce
    Générateur 7-bag : chaque tranche de 7 tirages consécutifs est une permutation
    des sept pièces. Deux Bag de même graine produisent la même suite.

--- tetris.Game ---
    Game(pieces, width=10, height=20)
        `pieces` est un itérable de noms de pièces, consommé à la demande.
    .board .score .level .lines_cleared .game_over
    .piece                Piece courante
    .row .col             position du coin haut-gauche de la matrice courante
    .cells()              frozenset des cellules ABSOLUES de la pièce courante
    .move(dcol)           -> bool ; décale horizontalement, False si bloqué
    .rotate(turns=1)      -> bool ; rotation avec dégagement (voir plus bas)
    .soft_drop()          -> bool ; descend d'une ligne. +1 point si réussi.
    .hard_drop()          -> int ; descend jusqu'au contact, retourne le nombre de
                             lignes parcourues, +2 points par ligne, PUIS verrouille
    .tick()               -> None ; gravité d'une ligne ; si bloqué, verrouille

Apparition : `row = 0`, `col = (width - piece.size) // 2`. Si la pièce qui apparaît
est déjà en collision, `game_over` passe à True.

Verrouillage : les cellules sont posées sur le plateau, les lignes pleines retirées,
le score et le niveau mis à jour, puis la pièce suivante apparaît.

Dégagement de rotation ("wall kick") : on tente la rotation en place ; si elle
collisionne, on essaie de décaler la pièce de -1 colonne, puis +1, puis pour la
pièce "I" seulement -2 puis +2. Le premier décalage libre est retenu et `col` est
mis à jour. Si aucun ne convient, la rotation échoue et rien ne change.

Score de lignes : 1 -> 100, 2 -> 300, 3 -> 500, 4 -> 800, multiplié par le niveau
courant AVANT mise à jour du niveau. Niveau initial 1, il vaut
`1 + lines_cleared // 10`.
"""

import pytest

from tetris import Bag, Board, Game, Piece, SHAPES


# --- SHAPES ---------------------------------------------------------------


def test_les_sept_pieces_existent():
    assert set(SHAPES) == set("IOTSZJL")


def test_matrices_imposees():
    assert SHAPES["I"] == ["....", "####", "....", "...."]
    assert SHAPES["O"] == ["##", "##"]
    assert SHAPES["T"] == [".#.", "###", "..."]
    assert SHAPES["S"] == [".##", "##.", "..."]
    assert SHAPES["Z"] == ["##.", ".##", "..."]
    assert SHAPES["J"] == ["#..", "###", "..."]
    assert SHAPES["L"] == ["..#", "###", "..."]


def test_chaque_piece_a_quatre_cellules():
    for name in SHAPES:
        assert len(Piece(name).cells()) == 4, name


# --- Piece ----------------------------------------------------------------


def test_cellules_de_T_en_rotation_zero():
    assert Piece("T").cells() == frozenset({(0, 1), (1, 0), (1, 1), (1, 2)})


def test_cellules_de_I_en_rotation_zero():
    assert Piece("I").cells() == frozenset({(1, 0), (1, 1), (1, 2), (1, 3)})


def test_taille_de_la_matrice():
    assert Piece("I").size == 4
    assert Piece("O").size == 2
    assert Piece("T").size == 3


def test_rotation_horaire_de_T():
    # [".#.",        [".#.",
    #  "###",   ->     ".##",     la colonne 0 lue de bas en haut devient la ligne 0
    #  "..."]          ".#."]
    assert Piece("T").rotated(1).cells() == frozenset({(0, 1), (1, 1), (1, 2), (2, 1)})


def test_rotation_horaire_de_I_devient_verticale():
    assert Piece("I").rotated(1).cells() == frozenset(
        {(0, 2), (1, 2), (2, 2), (3, 2)}
    )


def test_O_est_invariante_par_rotation():
    base = Piece("O").cells()
    for turns in range(1, 5):
        assert Piece("O").rotated(turns).cells() == base


def test_quatre_rotations_reviennent_a_l_origine():
    for name in SHAPES:
        assert Piece(name).rotated(4).cells() == Piece(name).cells(), name


def test_rotation_est_cyclique_modulo_quatre():
    assert Piece("T").rotated(5).rotation == 1
    assert Piece("T").rotated(-1).rotation == 3
    assert Piece("T").rotated(-1).cells() == Piece("T").rotated(3).cells()


def test_rotated_ne_modifie_pas_la_piece_source():
    piece = Piece("L")
    avant = piece.cells()
    piece.rotated(2)
    assert piece.cells() == avant
    assert piece.rotation == 0


# --- Board ----------------------------------------------------------------


def test_dimensions_par_defaut():
    board = Board()
    assert (board.width, board.height) == (10, 20)


def test_is_inside_aux_bords():
    board = Board(10, 20)
    assert board.is_inside(0, 0)
    assert board.is_inside(19, 9)
    assert not board.is_inside(-1, 0)
    assert not board.is_inside(0, -1)
    assert not board.is_inside(20, 0)
    assert not board.is_inside(0, 10)


def test_plateau_neuf_est_libre():
    board = Board(4, 4)
    assert board.is_free({(0, 0), (3, 3)})
    assert not board.occupied(2, 2)


def test_is_free_est_faux_hors_plateau():
    board = Board(4, 4)
    assert not board.is_free({(0, 0), (4, 0)})
    assert not board.is_free({(0, -1)})


def test_place_puis_occupied():
    board = Board(4, 4)
    board.place({(1, 1), (1, 2)})
    assert board.occupied(1, 1)
    assert board.occupied(1, 2)
    assert not board.occupied(1, 3)
    assert not board.is_free({(1, 1)})


def test_full_rows_detecte_une_ligne_pleine():
    board = Board(3, 3)
    board.place({(2, 0), (2, 1), (2, 2)})
    assert board.full_rows() == [2]


def test_clear_lines_retire_et_fait_descendre():
    board = Board(3, 3)
    board.place({(1, 0)})                       # un bloc isolé au-dessus
    board.place({(2, 0), (2, 1), (2, 2)})       # ligne pleine en bas
    assert board.clear_lines() == 1
    assert board.full_rows() == []
    assert board.occupied(2, 0)                 # le bloc isolé est descendu
    assert not board.occupied(1, 0)


def test_clear_lines_gere_plusieurs_lignes():
    board = Board(3, 4)
    board.place({(0, 0)})
    board.place({(2, 0), (2, 1), (2, 2)})
    board.place({(3, 0), (3, 1), (3, 2)})
    assert board.clear_lines() == 2
    assert board.occupied(2, 0)      # descendu de 2 lignes, pas jusqu'au fond
    assert not board.occupied(0, 0)
    assert board.full_rows() == []


def test_clear_lines_sans_ligne_pleine_ne_touche_a_rien():
    board = Board(3, 3)
    board.place({(2, 0)})
    assert board.clear_lines() == 0
    assert board.occupied(2, 0)


# --- Bag ------------------------------------------------------------------


def test_chaque_tranche_de_sept_est_une_permutation():
    bag = Bag(seed=1)
    for _ in range(4):
        tirage = [next(bag) for _ in range(7)]
        assert sorted(tirage) == sorted("IOTSZJL")


def test_meme_graine_meme_suite():
    a = [next(Bag(seed=42)) for _ in range(14)]
    b = [next(Bag(seed=42)) for _ in range(14)]
    assert a == b


def test_graines_differentes_donnent_des_suites_differentes():
    suites = {
        tuple(next(Bag(seed=graine)) for _ in range(14)) for graine in range(12)
    }
    assert len(suites) > 1


# --- Game : apparition et déplacement -------------------------------------


def test_apparition_centree():
    game = Game(iter(["T"]))
    assert game.row == 0
    assert game.col == 3
    assert game.piece.name == "T"
    assert not game.game_over


def test_apparition_de_O_est_centree_selon_sa_taille():
    game = Game(iter(["O"]))
    assert game.col == 4


def test_cells_sont_absolues():
    game = Game(iter(["T"]))
    assert game.cells() == frozenset({(0, 4), (1, 3), (1, 4), (1, 5)})


def test_move_decale_et_retourne_vrai():
    game = Game(iter(["T"]))
    assert game.move(-1) is True
    assert game.col == 2


def test_move_bloque_par_le_mur_gauche():
    game = Game(iter(["T"]))
    while game.move(-1):
        pass
    assert game.col == 0  # la colonne 0 de la matrice de T porte une cellule
    assert game.move(-1) is False
    assert min(col for _, col in game.cells()) == 0


def test_move_bloque_par_le_mur_droit():
    game = Game(iter(["O"]))
    while game.move(1):
        pass
    assert game.move(1) is False
    assert max(col for _, col in game.cells()) == 9


def test_etat_initial_du_score():
    game = Game(iter(["T"]))
    assert game.score == 0
    assert game.level == 1
    assert game.lines_cleared == 0


# --- Game : gravité et verrouillage ---------------------------------------


def test_tick_fait_descendre():
    game = Game(iter(["T", "T"]))
    game.tick()
    assert game.row == 1


def test_la_piece_se_verrouille_au_fond_et_la_suivante_apparait():
    game = Game(iter(["O", "T"]))
    for _ in range(19):   # 18 pour descendre, le 19e verrouille et fait apparaitre
        game.tick()
    assert game.piece.name == "T"
    assert game.row == 0
    assert game.board.occupied(19, 4)
    assert game.board.occupied(19, 5)
    assert game.board.occupied(18, 4)


def test_une_piece_se_pose_sur_une_autre():
    game = Game(iter(["O", "O", "T"]))
    for _ in range(40):
        game.tick()
    assert game.board.occupied(17, 4)
    assert game.board.occupied(16, 4)
    assert not game.board.occupied(15, 4)


def test_hard_drop_retourne_la_distance_et_verrouille():
    game = Game(iter(["O", "T"]))
    distance = game.hard_drop()
    assert distance == 18
    assert game.score == 36
    assert game.board.occupied(19, 4)
    assert game.piece.name == "T"


def test_soft_drop_donne_un_point():
    game = Game(iter(["T", "T"]))
    assert game.soft_drop() is True
    assert game.row == 1
    assert game.score == 1


def test_soft_drop_echoue_au_fond():
    game = Game(iter(["O", "O"]))
    while game.row < 18:
        game.soft_drop()
    assert game.soft_drop() is False


# --- Game : rotation avec dégagement --------------------------------------


def test_rotation_simple_en_place():
    game = Game(iter(["T"]))
    assert game.rotate(1) is True
    assert game.piece.rotation == 1


def test_rotation_contre_le_mur_droit_decale_la_piece():
    game = Game(iter(["I"]))
    assert game.rotate(1) is True        # verticale
    while game.move(1):
        pass
    assert game.col == 7
    col_avant = game.col
    assert game.rotate(1) is True        # redevient horizontale : deborde, doit decaler
    assert game.col < col_avant
    assert game.board.is_free(game.cells())


def test_rotation_impossible_ne_change_rien():
    # Plateau 3x3 : T occupe les lignes 0-1, la rotation exigerait la ligne 2 que
    # l'on mure. Aucun décalage (-1, +1) ne libère quoi que ce soit.
    game = Game(iter(["T"]), width=3, height=3)
    game.board.place({(2, 0), (2, 1), (2, 2)})
    avant = (game.col, game.piece.rotation, game.cells())
    assert game.rotate(1) is False
    assert (game.col, game.piece.rotation, game.cells()) == avant


# --- Game : lignes, score, niveau -----------------------------------------


def remplir_ligne_sauf(game, row, colonnes_libres):
    game.board.place(
        {(row, col) for col in range(game.board.width) if col not in colonnes_libres}
    )


def test_deux_lignes_completes_rapportent_trois_cents():
    game = Game(iter(["O", "T"]), width=10, height=20)
    remplir_ligne_sauf(game, 19, {4, 5})
    remplir_ligne_sauf(game, 18, {4, 5})
    game.hard_drop()
    assert game.lines_cleared == 2
    assert game.score == 36 + 300


def test_le_niveau_monte_tous_les_dix_lignes():
    game = Game(iter("O" * 20))
    game.lines_cleared = 0
    for row in range(19, 9, -1):
        remplir_ligne_sauf(game, row, {4, 5})
    # dix lignes ne manquent que de la colonne 4 et 5 : cinq O les complètent
    for _ in range(5):
        game.hard_drop()
    assert game.lines_cleared == 10
    assert game.level == 2


def empiler_jusqu_en_haut(game):
    """Remplit les colonnes 4 et 5 de la ligne 2 au fond, sans compléter de ligne."""
    for row in range(2, game.board.height):
        game.board.place({(row, 4), (row, 5)})


def test_game_over_quand_la_piece_ne_peut_pas_apparaitre():
    game = Game(iter(["O", "O"]))
    empiler_jusqu_en_haut(game)
    assert game.hard_drop() == 0      # la O courante est déjà au contact
    assert game.game_over is True     # la suivante n'a plus de place


def test_partie_terminee_le_tick_ne_fait_plus_rien():
    game = Game(iter(["O", "O"]))
    empiler_jusqu_en_haut(game)
    game.hard_drop()
    assert game.game_over is True
    etat = (game.row, game.col, game.score, game.lines_cleared)
    game.tick()
    assert (game.row, game.col, game.score, game.lines_cleared) == etat

"""colonnes — jeu de chute de tuiles."""


class Colonne:
    """Une pièce du jeu : trois tuiles empilées dans une seule colonne."""

    def __init__(self, tuiles):
        tuiles = tuple(tuiles)
        if len(tuiles) != 3:
            raise ValueError("La colonne doit contenir exactement trois tuiles")
        self.tuiles = tuiles

    def __eq__(self, other):
        if not isinstance(other, Colonne):
            return False
        return self.tuiles == other.tuiles

    def cycler(self):
        """Rend une nouvelle colonne où la tuile du bas est remontée au sommet."""
        a, b, c = self.tuiles
        return Colonne((c, a, b))

    def __repr__(self):
        return f"Colonne({self.tuiles!r})"


class Plateau:
    """Une grille de cases, chacune vide ou portant une tuile."""

    def __init__(self, largeur=6, hauteur=13):
        self.largeur = largeur
        self.hauteur = hauteur
        self._cases = [[None for _ in range(largeur)] for _ in range(hauteur)]

    def dedans(self, ligne, colonne):
        """La case est-elle dans la grille ?"""
        return 0 <= ligne < self.hauteur and 0 <= colonne < self.largeur

    def case(self, ligne, colonne):
        """La tuile, ou None si la case est vide ou hors grille."""
        if not self.dedans(ligne, colonne):
            return None
        return self._cases[ligne][colonne]

    def libre(self, ligne, colonne):
        """Dans la grille ET vide."""
        if not self.dedans(ligne, colonne):
            return False
        return self._cases[ligne][colonne] is None

    def poser(self, ligne, colonne, tuile):
        """Place une tuile. Hors grille → IndexError."""
        if not self.dedans(ligne, colonne):
            raise IndexError(f"({ligne}, {colonne}) hors grille")
        self._cases[ligne][colonne] = tuile

    def rendu(self):
        """String representation de la grille."""
        lignes = []
        for l in range(self.hauteur):
            lignes.append("".join(
                self._cases[l][c] if self._cases[l][c] is not None else "."
                for c in range(self.largeur)
            ))
        return "\n".join(lignes)

    def tasser(self):
        """Dans chaque colonne, les tuiles tombent jusqu'à reposer sur le fond ou
        sur une autre tuile. Leur ordre relatif est conservé."""
        for c in range(self.largeur):
            tuiles_col = [
                self._cases[l][c]
                for l in range(self.hauteur)
                if self._cases[l][c] is not None
            ]
            # Remplir le bas avec les tuiles, le haut avec None
            nb_vide = self.hauteur - len(tuiles_col)
            for l in range(self.hauteur):
                if l < nb_vide:
                    self._cases[l][c] = None
                else:
                    self._cases[l][c] = tuiles_col[l - nb_vide]


def alignements(plateau):
    """Rend l'ensemble des couples (ligne, colonne) des cases appartenant à au moins
    une suite de trois tuiles identiques ou plus.

    Quatre axes : horizontal, vertical, diagonale descendante, diagonale montante."""
    result = set()
    hauteur = plateau.hauteur
    largeur = plateau.largeur

    # Directions : (dligne, dcol)
    directions = [
        (0, 1),   # horizontal
        (1, 0),   # vertical
        (1, 1),   # diagonale descendante
        (-1, 1),  # diagonale montante
    ]

    for dligne, dcol in directions:
        for l in range(hauteur):
            for c in range(largeur):
                tuile = plateau.case(l, c)
                if tuile is None:
                    continue
                # On regarde en aval
                suite = [(l, c)]
                nl, nc = l + dligne, c + dcol
                while plateau.dedans(nl, nc) and plateau.case(nl, nc) == tuile:
                    suite.append((nl, nc))
                    nl += dligne
                    nc += dcol
                if len(suite) >= 3:
                    result.update(suite)

    return result


class Jeu:
    """Jeu de chute de tuiles."""

    def __init__(self, sequence, largeur=6, hauteur=13):
        self.plateau = Plateau(largeur, hauteur)
        self._sequence = iter(sequence)
        self._largeur = largeur
        self._hauteur = hauteur
        self.col = largeur // 2
        self.ligne = 0
        self._chaine_max = 0
        self._tuiles_supprimees = 0
        self._score = 0
        self.partie_terminee = False
        self._verrouiller_suivant()

    def _verrouiller_suivant(self):
        """Preparer la colonne suivante."""
        try:
            tuiles_str = next(self._sequence)
            self.colonne = Colonne(tuiles_str)
            self.ligne = 0
            self.col = self._largeur // 2
            # Vérifier l'apparition n'est pas bloquée
            for i in range(3):
                if not self.plateau.libre(self.ligne + i, self.col):
                    self.colonne = None
                    self.partie_terminee = True
                    return
        except StopIteration:
            self.colonne = None
            self.partie_terminee = True

    def _verrouiller_colonne(self):
        """Verrouiller la colonne sur le plateau, résoudre alignements, faire apparaître
        la colonne suivante."""
        if self.colonne is None:
            return

        # Poser les tuiles sur le plateau
        for i, tuile in enumerate(self.colonne.tuiles):
            self.plateau.poser(self.ligne + i, self.col, tuile)

        # Boucle : chercher alignements, supprimer, tass, jusqu'à ce qu'il n'y en ait plus
        tuiles_supprimees_total = 0
        scores_pass = []

        while True:
            al = alignements(self.plateau)
            if not al:
                break
            tuiles_supprimees_total += len(al)
            scores_pass.append(len(al))

            # Supprimer les alignements
            for (l, c) in al:
                self.plateau._cases[l][c] = None

            # Tasser
            self.plateau.tasser()

        # Calculer le score et la chaine
        if scores_pass:
            self._chaine_max = len(scores_pass)
            multiplicateur = 1
            for nb_cases in scores_pass:
                self._score += nb_cases * 10 * multiplicateur
                multiplicateur = min(multiplicateur * 2, 16)

        self._tuiles_supprimees += tuiles_supprimees_total

        # Faire apparaître la colonne suivante
        self._verrouiller_suivant()

    def cellules(self):
        """{ (ligne, colonne) : tuile } pour les trois tuiles de la colonne en chute."""
        if self.colonne is None:
            return {}
        return {
            (self.ligne, self.col): self.colonne.tuiles[0],
            (self.ligne + 1, self.col): self.colonne.tuiles[1],
            (self.ligne + 2, self.col): self.colonne.tuiles[2],
        }

    def deplacer(self, dcol):
        """Décale d'une colonne si les trois cases visées sont libres."""
        if self.colonne is None or self.partie_terminee:
            return False
        new_col = self.col + dcol
        for i in range(3):
            if not self.plateau.libre(self.ligne + i, new_col):
                return False
        self.col = new_col
        return True

    def cycler(self):
        """Cycle la colonne en chute."""
        if self.colonne is None or self.partie_terminee:
            return False
        self.colonne = self.colonne.cycler()
        return True

    def descendre(self):
        """Descendre d'une ligne si c'est libre."""
        if self.colonne is None or self.partie_terminee:
            return False
        new_ligne = self.ligne + 1
        if new_ligne + 2 >= self._hauteur:
            return False
        for i in range(3):
            if not self.plateau.libre(new_ligne + i, self.col):
                return False
        self.ligne = new_ligne
        return True

    def chuter(self):
        """Descendre jusqu'au blocage, verrouiller la colonne, résoudre alignements,
        faire apparaître la colonne suivante. Rend le nombre de lignes parcourues."""
        if self.colonne is None:
            return 0

        lignes_parcourues = 0
        while self.descendre():
            lignes_parcourues += 1

        # Verrouiller
        self._verrouiller_colonne()

        return lignes_parcourues

    def tick(self):
        """Descendre d'une ligne, ou verrouille si la descente est impossible."""
        if self.colonne is None or self.partie_terminee:
            return

        if not self.descendre():
            # Verrouiller
            self._verrouiller_colonne()

    @property
    def chaine_max(self):
        return self._chaine_max

    @property
    def tuiles_supprimees(self):
        return self._tuiles_supprimees

    @property
    def score(self):
        return self._score

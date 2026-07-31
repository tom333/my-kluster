from .shapes import SHAPES

class Piece:
    def __init__(self, name, rotation=0):
        self.name = name
        self.rotation = rotation % 4
        self.size = len(SHAPES[name])
        self.matrix = self._get_matrix(name, rotation)

    def _get_matrix(self, name, rotation):
        base_matrix = SHAPES[name]
        size = len(base_matrix)
        
        # Perform rotation 'rotation' times
        current_matrix = [list(row) for row in base_matrix]
        for _ in range(rotation):
            new_matrix = [['' for _ in range(size)] for _ in range(size)]
            for r in range(size):
                for c in range(size):
                    new_matrix[c][size - 1 - r] = current_matrix[r][c]
            current_matrix = new_matrix
        return current_matrix

    def cells(self):
        cells = set()
        for r, row in enumerate(self.matrix):
            for c, char in enumerate(row):
                if char == '#':
                    cells.add((r, c))
        return frozenset(cells)

    def rotated(self, turns):
        new_rotation = (self.rotation + turns) % 4
        return Piece(self.name, new_rotation)

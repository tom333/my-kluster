from .shapes import SHAPES
from .piece import Piece
from .board import Board

class Game:
    def __init__(self, pieces, width=10, height=20):
        self.width = width
        self.height = height
        self.board = Board(width, height)
        self.pieces = pieces
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        
        self.next_piece_name = next(self.pieces, None)
        if self.next_piece_name is None:
            self.game_over = True
            return

        self.piece = Piece(self.next_piece_name)
        self.row = 0
        self.col = (self.width - self.piece.size) // 2
        
        if not self.board.is_free(self._get_absolute_cells()):
            self.game_over = True

    def _get_absolute_cells(self):
        return {(r + self.row, c + self.col) for r, c in self.piece.cells()}

    def cells(self):
        return self._get_absolute_cells()

    def _get_piece_width(self):
        cells = self.piece.cells()
        return max(c for r, c in cells) - min(c for r, c in cells) + 1

    def move(self, dcol):
        if self.game_over:
            return False
        new_col = self.col + dcol
        width = self._get_piece_width()
        if 0 <= new_col and new_col + width <= self.width:
            new_cells = {(r + self.row, c + new_col) for r, c in self.piece.cells()}
            if self.board.is_free(new_cells):
                self.col = new_col
                return True
        return False

    def rotate(self, turns=1):
        if self.game_over:
            return False
        
        target_rotation = (self.piece.rotation + turns) % 4
        new_piece = Piece(self.piece.name, target_rotation)
        
        offsets = [0]
        if self.piece.name != "I":
            offsets += [-1, 1]
        else:
            offsets += [-1, 1, -2, 2]
            
        for offset in offsets:
            new_c = self.col + offset
            new_width = self._get_piece_width_for_piece(new_piece)
            if 0 <= new_c and new_c + new_width <= self.width:
                new_cells = {(r + self.row, c + new_c) for r, c in new_piece.cells()}
                if self.board.is_free(new_cells):
                    self.piece = new_piece
                    self.col = new_c
                    return True
        return False

    def _get_piece_width_for_piece(self, piece):
        cells = piece.cells()
        return max(c for r, c in cells) - min(c for r, c in cells) + 1

    def soft_drop(self):
        if self.game_over:
            return False
        if self.row + 1 < self.height:
            new_cells = {(r + self.row + 1, c + self.col) for r, c in self.piece.cells()}
            if self.board.is_free(new_cells):
                self.row += 1
                self.score += 1
                return True
        return False

    def hard_drop(self):
        if self.game_over:
            return 0
        
        count = 0
        while self.row + 1 < self.height:
            new_cells = {(r + self.row + 1, c + self.col) for r, c in self.piece.cells()}
            if self.board.is_free(new_cells):
                self.row += 1
                count += 1
            else:
                break
        
        self.score += count * 2
        self._lock()
        return count

    def _lock(self):
        self.board.place(self._get_absolute_cells())
        num_cleared = self.board.clear_lines()
        self.lines_cleared += num_cleared
        
        scores_map = {1: 100, 2: 300, 3: 500, 4: 800}
        if num_cleared > 0:
            self.score += scores_map.get(num_cleared, 0) * self.level
        
        self.level = 1 + self.lines_cleared // 10
        
        self.next_piece_name = next(self.pieces, None)
        if self.next_piece_name is None:
            self.game_over = True
            return

        self.piece = Piece(self.next_piece_name)
        self.row = 0
        self.col = (self.width - self.piece.size) // 2
        
        if not self.board.is_free(self._get_absolute_cells()):
            self.game_over = True

    def tick(self):
        if self.game_over:
            return
        
        if not self.soft_drop():
            self._lock()

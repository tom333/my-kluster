class Board:
    def __init__(self, width=10, height=20):
        self.width = width
        self.height = height
        self.grid = [[False for _ in range(width)] for _ in range(height)]

    def is_inside(self, row, col):
        return 0 <= row < self.height and 0 <= col < self.width

    def is_free(self, cells):
        for r, c in cells:
            if not self.is_inside(r, c) or self.grid[r][c]:
                return False
        return True

    def place(self, cells):
        for r, c in cells:
            self.grid[r][c] = True

    def occupied(self, row, col):
        if not self.is_inside(row, col):
            return False
        return self.grid[row][col]

    def full_rows(self):
        full_rows = []
        for r in range(self.height):
            if all(self.grid[r][c] for c in range(self.width)):
                full_rows.append(r)
        return sorted(full_rows)

    def clear_lines(self):
        full_rows = self.full_rows()
        num_cleared = len(full_rows)
        if num_cleared == 0:
            return 0
        
        new_grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        # Copy rows that are not full
        full_set = set(full_rows)
        current_new_row = self.height - 1
        
        # We iterate from bottom to top to fill the new grid
        # Wait, the rows that are NOT full should be moved down.
        # Actually, it's easier to just rebuild the grid.
        
        # Let's rethink.
        # Example: 4 rows. Rows 2 and 3 are full.
        # Row 0, 1 remain.
        # New grid: 
        # Row 0: Row 0
        # Row 1: Row 1
        # Row 2: Empty
        # Row 3: Empty
        # No, that's not right. The rows above the cleared rows should fall down.
        
        # Let's do it this way:
        new_grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        # The rows that are NOT full are kept in their relative order.
        # The rows that ARE full are removed, and the ones above them fall down.
        
        # Let's track which rows to keep.
        rows_to_keep = [r for r in range(self.height) if r not in full_set]
        
        # The new rows at the bottom (the ones that were cleared) are now empty.
        # Actually, the new grid should have the kept rows at the bottom.
        # Wait, the prompt says "fait descendre ce qui est au-dessus".
        # Let's say we have 4 rows (0, 1, 2, 3). 2 and 3 are full.
        # Row 0 and 1 are kept. They should move to the bottom.
        # So new grid will have:
        # Row 0: Empty
        # Row 1: Empty
        # Row 2: Row 0
        # Row 3: Row 1
        
        # Wait, that's not how Tetris works.
        # In Tetris, if row 3 is full, it's removed, and row 2 becomes row 3.
        # If row 2 is also full, it's removed, and row 1 becomes row 2.
        # So row 1 becomes row 3.
        
        # Let's re-examine:
        # row 0: .
        # row 1: .
        # row 2: full
        # row 3: full
        # Clear 2 and 3.
        # row 0 becomes row 2.
        # row 1 becomes row 3.
        # So new grid:
        # row 0: empty
        # row 1: empty
        # row 2: row 0
        # row 3: row 1
        
        # Let's try this logic:
        # The rows are kept in order. Let's say we have rows R0, R1, R2, R3.
        # If R3 is full, it's gone. R0, R1, R2 are kept.
        # The new grid will have R0, R1, R2 at the bottom.
        # If R2 is also full, it's also gone. R0, R1 are kept.
        # The new grid will have R0, R1 at the bottom.
        
        # Let's implement this.
        # We can iterate from bottom to top.
        
        # Actually, it's simpler:
        # New grid is filled from the bottom.
        # The rows that are not full are copied into the new grid starting from the bottom.
        
        # Let's try this:
        new_grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        # Rows to keep (in original order)
        rows_to_keep = [r for r in range(self.height) if r not in full_set]
        # These rows should be placed at the bottom of the new_grid.
        # Wait, if row 2 is cleared, row 1 moves to 2.
        # If row 3 is cleared, row 2 moves to 3.
        # So if row 2 and 3 are cleared, row 1 moves to 3, and row 0 moves to 2.
        # This means the rows are kept and their new indices are:
        # new_idx = original_idx - number_of_cleared_rows_below_it
        
        # Let's just build the new_grid.
        # The rows that were NOT full:
        # For each such row r, its new position is r - (number of full rows < r)
        # No, that's not right. It's r - (number of full rows >= r).
        # Let's check:
        # Row 0, 1, 2, 3. 2 and 3 are full.
        # r=0: full rows >= 0 are {2, 3}. count=2. new_r = 0 - 2 = -2. (Wrong)
        # Let's try r - (number of full rows < r).
        # r=0: full rows < 0 is {}. count=0. new_r = 0.
        # r=1: full rows < 1 is {}. count=0. new_r = 1.
        # r=2: full rows < 2 is {}. count=0.
        # This doesn't move them down.
        
        # Let's do it properly.
        # The rows that are NOT full are preserved.
        # The number of full rows is `num_cleared`.
        # The new grid will have these rows shifted down.
        # Let's iterate through the rows from 0 to height-1.
        # If a row is not full, it stays in its relative order.
        # The number of rows below it that were cleared determines its new position.
        
        # Actually, let's just do this:
        # 1. Identify all full rows.
        # 2. Create a new grid.
        # 3. For each row r in 0..height-1:
        #    If r is not full, find its new position.
        #    Its new position is r - (number of full rows that were < r).
        #    Wait, that's not right either.
        
        # Let's use a simpler approach:
        # Create a list of rows that are not full.
        # These rows will be placed at the bottom of the new grid.
        # But wait, they should be placed such that they stay in their relative order.
        # Let's say original rows are R0, R1, R2, R3.
        # If R2 and R3 are full.
        # They are removed. R0 and R1 remain.
        # In the new grid, R0 will be at index 2, R1 will be at index 3.
        # Wait, no! R0 should be at index 2, R1 at index 3?
        # Let's see. If R3 was full, R2 moves to 3. If R2 was full, R1 moves to 2.
        # So R1 moves to 3, and R0 moves to 2.
        # Yes! So the new row index for a non-full row r is:
        # new_r = r - (number of full rows with index < r)
        # Let's test:
        # Row 0, 1, 2, 3. Full rows are {2, 3}.
        # r=0: full rows < 0: 0. new_r = 0. (Still 0)
        # r=1: full rows < 1: 0. new_r = 1. (Still 1)
        # If R1 was also full. Full rows are {1, 2, 3}.
        # r=0: full rows < 0: 0. new_r = 0. (Still 0)
        # Wait, if R1 is full, R0 should move to 1.
        
        # Let's try: new_r = r - (number of full rows with index <= r)
        # Wait, if r=0 and R0 is full, new_r = 0 - 1 = -1.
        
        # Let's do this:
        # The rows that are NOT full are R_i1, R_i2, ...
        # They will be placed in the new grid at the bottom.
        # If we have N rows total, and we kept K rows, they will occupy
        # indices (height-K) to (height-1).
        # No, that's if only the bottom ones were removed.
        
        # Let's look at the example again.
        # 0: .
        # 1: .
        # 2: full
        # 3: full
        # Clear 2 and 3. R0 and R1 remain.
        # They should move down to 2 and 3.
        # So the new grid should be:
        # 0: empty
        # 1: empty
        # 2: R0
        # 3: R1
        # In this case, the new indices are:
        # r=0 -> new_r = 2
        # r=1 -> new_r = 3
        # The number of full rows is 2.
        # So new_r = r + (number of full rows that were >= r)? No.
        
        # Let's just do it this way:
        # 1. Get full rows.
        # 2. Create new_grid.
        # 3. Pointer for new_grid: p = height - 1.
        # 4. Iterate r from height-1 down to 0:
        #    If r is not full:
        #       new_grid[p] = grid[r]
        #       p -= 1
        # Wait, if R3 was full, R2 should move to 3.
        # If we go from bottom to top:
        # r=3: full. p stays 3.
        # r=2: full. p stays 3.
        # r=1: not full. new_grid[3] = grid[1]. p becomes 2.
        # r=0: not full. new_grid[2] = grid[0]. p becomes 1.
        # Result:
        # new_grid[0] = empty
        # new_grid[1] = empty
        # new_grid[2] = grid[0]
        # new_grid[3] = grid[1]
        # This is exactly what we want!
        
        new_grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        p = self.height - 1
        for r in range(self.height - 1, -1, -1):
            if r not in full_set:
                new_grid[p] = list(self.grid[r])
                p -= 1
        self.grid = new_grid
        return num_cleared

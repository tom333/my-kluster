import random

class Bag:
    def __init__(self, seed):
        self.random = random.Random(seed)
        self.pieces = []
        self.fill_bag()

    def fill_bag(self):
        # Each bag is a permutation of the 7 pieces
        all_pieces = ["I", "O", "T", "S", "Z", "J", "L"]
        # Use random.sample to get a permutation
        self.pieces = self.random.sample(all_pieces, len(all_pieces))

    def __next__(self):
        if not self.pieces:
            self.fill_bag()
        return self.pieces.pop(0)

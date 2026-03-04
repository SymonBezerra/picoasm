from chr_rom import CharacterROM


class Tile:
    TILE_BLOCKS = 4

    def __init__(self):
        self.blocks = [0 for _ in range(Tile.TILE_BLOCKS)]

    # how can I code an expression like
    # tile << (0b01 << 4)
    def __lshift__(self, other):
        if not isinstance(other, int):
            raise TypeError("__lshift__ (<<) expects an integer")
        if other < 0 or other > 0xFF:
            raise ValueError("__lshift__ (<<) expects an integer between 0 and 255")
        for i in range(Tile.TILE_BLOCKS):
            self.blocks[i] = (other >> (i * 2)) & 0b11
        return self


class TileSet:
    def __init__(self):
        self.tiles = [
            Tile() for _ in range(CharacterROM.CHRROM_SIZE // Tile.TILE_BLOCKS)
        ]

    def compile(self, path):
        with open(path, "wb") as f:
            f.write("picoASM".encode("ascii"))
            f.write(len(self.tiles).to_bytes(2, byteorder="little"))
            for tile in self.tiles:
                for block in tile.blocks:
                    f.write(block.to_bytes(1, byteorder="little"))

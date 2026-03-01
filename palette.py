class PaletteRAM:
    START_ADDR = 0xD900
    SIZE = 0x0400

    def __init__(self):
        self.memory = bytearray(PaletteRAM.SIZE)

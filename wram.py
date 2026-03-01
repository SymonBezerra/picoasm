class WorkRAM:
    START_ADDR = 0xB000
    WRAM_SIZE = 0x2000

    def __init__(self):
        self.memory = bytearray(WorkRAM.WRAM_SIZE)

class ProgramRAM:
    START_ADDR = 0xE500
    SIZE = 0x1000

    def __init__(self):
        self.memory = bytearray(ProgramRAM.SIZE)

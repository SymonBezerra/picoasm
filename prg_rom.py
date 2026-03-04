from io import BytesIO
import struct


class ProgramROM:
    START_ADDR = 0x0000
    BANK_SIZE = 0x4000

    def __init__(self, path):
        self.memory = bytearray(ProgramROM.BANK_SIZE)

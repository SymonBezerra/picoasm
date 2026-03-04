from io import BytesIO
import struct


# CHRROM is located after the banks
class CharacterROM:
    START_ADDR = 0x9000
    CHRROM_SIZE = 0x2000

    def __init__(self):
        self.memory = bytearray(CharacterROM.CHRROM_SIZE)

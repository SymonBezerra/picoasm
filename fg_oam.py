class ForegroundOAM:
    START_ADDR = 0xD800
    OAM_SIZE = 0x0100

    def __init__(self):
        self.memory = bytearray(ForegroundOAM.OAM_SIZE)

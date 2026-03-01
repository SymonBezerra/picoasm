class BackgroundOAM:
    START_ADDR = 0xD000
    OAM_SIZE = 0x0100

    def __init__(self):
        self.memory = bytearray(BackgroundOAM.OAM_SIZE)

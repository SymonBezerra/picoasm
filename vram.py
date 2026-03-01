class VideoRAM:
    START_ADDR = 0x8000
    SIZE = 0x1000

    def __init__(self):
        self.memory = bytearray(VideoRAM.SIZE)

class StackRAM:
    START_ADDR = 0xDD00
    STACK_SIZE = 0x0800

    def __init__(self):
        self.memory = bytearray(StackRAM.STACK_SIZE)

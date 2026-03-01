from io import BytesIO
import struct


# CHRROM is located after the banks
class CharacterROM:
    START_ADDR = 0x9000
    CHRROM_SIZE = 0x2000

    def __init__(self, path):
        def read(stream, fmt):
            size = struct.calcsize(fmt)
            data = stream.read(size)
            if not data:
                raise EOFError("End of file reached")
            return struct.unpack(fmt, data)[0]

        with open(path, "rb") as f:
            data = f.read()
        stream = BytesIO(data)
        stream.seek(7)
        banks_count = read(stream, "<B")
        for _ in range(banks_count):
            bank_size = read(stream, "<H")
            stream.seek(bank_size * 8, 1)
        self.memory = bytearray(stream.read())

from io import BytesIO
import struct


class ProgramROM:
    START_ADDR = 0x0000
    BANK_SIZE = 0x4000
    PRGROM_BANKS = (0x0000, 0x4000)

    def __init__(self, path):
        def read(stream, fmt):
            size = struct.calcsize(fmt)
            data = stream.read(size)
            if not data:
                raise EOFError("End of file reached")
            return struct.unpack(fmt, data)[0]

        with open(path, "rb") as f:
            data = f.read()
        self.banks_len = []
        stream = BytesIO(data)
        stream.seek(7)
        self.banks_count = read(stream, "<B")
        self.swap_bank = 1
        self.memory = bytearray(ProgramROM.BANK_SIZE * self.banks_count)

        # avoid GRAPHICS bank, which is the first one, and load only the program banks
        graphics_len = read(stream, "<H")
        stream.seek(graphics_len * 8, 1)

        for i in range(self.banks_count):
            bank_size = read(stream, "<H")
            self.banks_len.append(bank_size)
            start = ProgramROM.PRGROM_BANKS[i]
            bank_data = [read(stream, "<Q") for _ in range(bank_size)]
            rom = b"".join(instr.to_bytes(8, "little") for instr in bank_data)

            start = ProgramROM.PRGROM_BANKS[i]
            end = start + len(rom)

            max_end = ProgramROM.PRGROM_BANKS[i] + ProgramROM.BANK_SIZE

            if end > max_end:
                rom = rom[: max_end - start]

            self.memory[start : start + len(rom)] = rom

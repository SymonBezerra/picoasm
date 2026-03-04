from collections import defaultdict
import struct
from pathlib import Path
import os

from opcodes import OPCODES
from subroutine import SubRoutine


class Program:
    MAIN = "__main"

    def __init__(self):
        self.subroutines = defaultdict(list)

    def __lshift__(self, other: SubRoutine):
        if not isinstance(other, SubRoutine):
            raise TypeError("__lshift__ (<<) expects an instance of SubRoutine")
        self.subroutines[other.name].extend(other.instructions)

    def compile(self, path, entry_point=MAIN):
        if entry_point not in self.subroutines:
            raise ValueError(f"Entry point '{entry_point}' not found in subroutines")
        subroutines = dict()
        buffer = list()

        def compile(instr):
            opcode = instr[0]
            if opcode not in OPCODES:
                raise ValueError(f"Invalid opcode: {opcode}")
            if opcode == "GOSUB":
                target = instr[1]
                if target not in subroutines:
                    raise ValueError(
                        f"GOSUB target '{target}' not found in subroutines or not compiled yet (out of scope)"
                    )
                elif target == entry_point:
                    raise ValueError(
                        "GOSUB cannot call the entry point subroutine (recursive calls not supported)"
                    )
                return struct.pack("<BH", OPCODES["GOSUB"][0], subroutines[target])
            else:
                return struct.pack(OPCODES[opcode][2], OPCODES[opcode][0], *instr[1:])

        for name, subroutine in self.subroutines.items():
            if name == entry_point:
                continue
            subroutines[name] = len(buffer)
            for instr in subroutine:
                buffer.append(compile(instr))
        for instr in self.subroutines[entry_point]:
            subroutines[entry_point] = len(buffer)
            buffer.append(compile(instr))

        with open(path, "wb") as f:
            f.write(b"picoASM")
            f.write(struct.pack("<H", subroutines[entry_point]))
            for instr in buffer:
                f.write(instr)

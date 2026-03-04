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
        labels = dict()
        buffer = list()

        def compile(sub):
            for instr in sub:
                opcode = instr[0]
                if opcode not in OPCODES:
                    raise ValueError(f"Invalid opcode: {opcode}")
                if opcode == "LABEL":
                    labels[instr[1]] = len(buffer)
                    continue
                elif opcode == "JMP":
                    target = instr[1]
                    if target not in labels:
                        raise ValueError(
                            f"JMP target '{target}' not found in subroutine labels (out of scope)"
                        )
                    buffer.append(
                        struct.pack("<BH", OPCODES["JMP"][0], labels[target]).ljust(
                            8, b"\x00"
                        )
                    )
                elif opcode == "GOSUB":
                    target = instr[1]
                    if target not in subroutines:
                        raise ValueError(
                            f"GOSUB target '{target}' not found in subroutines or not compiled yet (out of scope)"
                        )
                    elif target == entry_point:
                        raise ValueError(
                            "GOSUB cannot call the entry point subroutine (recursive calls not supported)"
                        )
                    buffer.append(
                        struct.pack(
                            "<BH", OPCODES["GOSUB"][0], subroutines[target]
                        ).ljust(8, b"\x00")
                    )
                else:
                    buffer.append(
                        struct.pack(
                            OPCODES[opcode][2], OPCODES[opcode][0], *instr[1:]
                        ).ljust(8, b"\x00")
                    )

        for name, subroutine in self.subroutines.items():
            if name == entry_point:
                continue
            subroutines[name] = len(buffer)
            compile(subroutine)
        entrypoint_addr = len(buffer)
        compile(self.subroutines[entry_point])

        with open(path, "wb") as f:
            f.write(b"picoASM")
            f.write(struct.pack("<H", entrypoint_addr))
            for instr in buffer:
                f.write(instr)

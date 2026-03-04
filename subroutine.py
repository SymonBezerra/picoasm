from opcodes import OPCODES


class SubRoutine:
    def __init__(self, name: str):
        self.name = name
        self.__instructions = list()
        self.__labels = dict()

    @property
    def instructions(self):
        return self.__instructions

    @property
    def labels(self):
        return self.__labels

    def __lshift__(self, other: tuple):
        if not isinstance(other, tuple):
            raise TypeError("__lshift__ (<<) expects a tuple of (opcode, *args)")

        if other[0] in ("NOP", "INPUT", "OUTPUT", "VSYNC"):
            if len(other) != 1:
                raise ValueError(
                    f"Opcode '{other[0]}' expects no arguments, got {len(other) - 1}"
                )
            self.__instructions.append(other)
        else:
            try:
                opcode, *args = other
            except ValueError:
                raise ValueError("__lshift__ (<<) expects a tuple of (opcode, *args)")

            if opcode not in OPCODES:
                raise ValueError(f"Invalid opcode: {opcode}")
            if len(args) != OPCODES[opcode][1]:
                raise ValueError(
                    f"Opcode '{opcode}' expects {OPCODES[opcode][1]} arguments, got {len(args)}"
                )

            if opcode == "LABEL":
                self.__labels[args[0]] = len(self.__instructions)
            elif opcode == "JMP":
                if args[0] in self.__labels:
                    self.__instructions.append((opcode, self.__labels[args[0]]))
                else:
                    raise ValueError(
                        f"JMP target '{args[0]}' not found in subroutine labels (out of scope)"
                    )
            else:
                self.__instructions.append(other)

from opcodes import OPCODES


class SubRoutine:
    def __init__(self, name: str):
        self.name = name
        self.__instructions = list()

    @property
    def instructions(self):
        return self.__instructions

    def __lshift__(self, other: tuple):
        if not isinstance(other, tuple):
            raise TypeError("__lshift__ (<<) expects a tuple of (opcode, *args)")

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

        self.__instructions.append(other)

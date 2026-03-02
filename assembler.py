from argparse import ArgumentParser
from collections import defaultdict
from enum import Enum
import struct
from pathlib import Path
import os

parser = ArgumentParser()

parser.add_argument("FILES", nargs="+", help="Path to the picoASM source files")
parser.add_argument(
    "-o", "--output", help="Path to the output binary file", default="output.bin"
)

args = parser.parse_args()


class OperandType(Enum):
    LITERAL = 0
    ADDRESS = 1


SYMBOLS = (
    "@",  # JMP,
    "+",  # ADD,
    "-",  # SUB,
    "#",  # MOV,
    "?",  # CGTZ,
    "=",  # CEQ,
    ",",  # INP,
    ".",  # OUT,
    "^",  # CRSJ,
    "<",  # CRSL,
    ">",  # CRSR,
    "!",  # VSYNC,
    "V",  # GOSUB,
    "A",  # RET
)


class Assembler:
    def __init__(self, paths):
        self.lines = list()
        for path in paths:
            with open(Path(os.path.join(os.getcwd(), path)), "r") as f:
                self.lines.append(f.readlines())

            self.instructions = defaultdict(list)
            self.macros = dict()
            self.labels = dict()

    def tokenize(self, line):
        tokens = []
        current = ""
        depth = 0
        for char in line:
            if char == "(":
                depth += 1
                current += char
            elif char == ")":
                depth -= 1
                current += char
                if depth == 0:
                    tokens.append(current)
                    current = ""
            elif char == " " and depth == 0:
                if current:
                    tokens.append(current)
                    current = ""
            else:
                current += char
        if current:
            tokens.append(current)
        return tokens

    def assemble(self):
        for lines in self.lines:
            header_line = lines[0].strip()
            if (
                not header_line.startswith("{")
                or not header_line.endswith("}")
                or (header_line.startswith("{{") and header_line.endswith("}}"))
            ):
                raise SyntaxError(
                    "First line must be a header in the format {bank_name}"
                )
            bank_name = header_line[1:-1].strip()
            i = 1
            while i < len(lines):
                line = lines[i].split(";")[0].strip()  # Remove comments and whitespace
                i += 1
                if not line:
                    continue  # Skip empty lines
                if (
                    line.startswith("{")
                    and line.endswith("}")
                    and not (line.startswith("{{") and line.endswith("}}"))
                ):
                    raise SyntaxError(
                        "Bank headers can only be defined on the first line"
                    )
                elif line.startswith("{{") and line.endswith("}}"):
                    with open(
                        Path(os.path.join(os.getcwd(), line[2:-2].strip())), "r"
                    ) as f:
                        included_lines = f.readlines()
                    lines = lines[: i - 1] + included_lines + lines[i:]
                elif line.startswith("%"):
                    tokens = self.tokenize(line[1:])
                    if len(tokens) != 2:
                        raise SyntaxError(f"Invalid macro definition: {line}")
                    macro_name = tokens[0]
                    macro_value = tokens[1]
                    self.macros[macro_name] = macro_value
                    # self.macros[line[1:]] = self.tokenize(line[1:])[1:]
                elif line.startswith(":"):
                    self.labels[line[1:]] = len(self.instructions[bank_name])
                elif line.startswith("@"):
                    # @ [literal or address value] [label or address]
                    parts = self.tokenize(line[1:])
                    if len(parts) != 2:
                        raise SyntaxError(f"Invalid JMP syntax: {line}")
                    try:
                        type, value = self.parse_operand_type(parts[0])
                        target = self.parse_addr(parts[1])
                    except Exception as e:
                        raise SyntaxError(f"Invalid JMP syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BBHH", SYMBOLS.index("@"), type.value, value, target
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith("#"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 2:
                        raise SyntaxError(f"Invalid MOV syntax: {line}")
                    try:
                        type, value = self.parse_operand_type(parts[0])
                        target_value = self.parse_addr(parts[1])
                    except Exception as e:
                        raise SyntaxError(f"Invalid MOV syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BBHH", SYMBOLS.index("#"), type.value, value, target_value
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith("+"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 2:
                        raise SyntaxError(f"Invalid ADD syntax: {line}")
                    try:
                        value = self.parse_value(parts[0])
                        target = self.parse_addr(parts[1])
                    except Exception as e:
                        raise SyntaxError(f"Invalid ADD syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack("<BBH", SYMBOLS.index("+"), value, target).ljust(
                            8, b"\x00"
                        )
                    )
                elif line.startswith("-"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 2:
                        raise SyntaxError(f"Invalid SUB syntax: {line}")
                    try:
                        value = self.parse_value(parts[0])
                        target = self.parse_addr(parts[1])
                    except Exception as e:
                        raise SyntaxError(f"Invalid SUB syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack("<BBH", SYMBOLS.index("-"), value, target).ljust(
                            8, b"\x00"
                        )
                    )
                elif line.startswith("?"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 2:
                        raise SyntaxError(f"Invalid CGTZ syntax: {line}")
                    try:
                        target = self.parse_addr(parts[0])
                        save_addr = self.parse_addr(parts[1])
                    except Exception as e:
                        raise SyntaxError(f"Invalid CGTZ syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BHH", SYMBOLS.index("?"), target, save_addr
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith("="):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 3:
                        raise SyntaxError(f"Invalid CEQ syntax: {line}")
                    try:
                        a1 = self.parse_addr(parts[0])
                        a2 = self.parse_addr(parts[1])
                        save_addr = self.parse_addr(parts[2])
                    except Exception as e:
                        raise SyntaxError(f"Invalid CEQ syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BHHH", SYMBOLS.index("="), a1, a2, save_addr
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith(","):
                    self.instructions[bank_name].append(
                        struct.pack("<B", SYMBOLS.index(",")).ljust(8, b"\x00")
                    )
                elif line.startswith("."):
                    self.instructions[bank_name].append(
                        struct.pack("<B", SYMBOLS.index(".")).ljust(8, b"\x00")
                    )
                elif line.startswith("^"):
                    parts = self.tokenize(line[1:])
                    try:
                        addr = self.parse_addr(parts[0])
                    except Exception as e:
                        raise SyntaxError(f"Invalid CRSJ syntax: {line}") from e
                    if len(parts) != 1:
                        raise SyntaxError(f"Invalid CRSJ syntax: {line}")
                    self.instructions[bank_name].append(
                        struct.pack("<BH", SYMBOLS.index("^"), addr).ljust(8, b"\x00")
                    )
                elif line.startswith("<"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 1:
                        raise SyntaxError(f"Invalid CRSL syntax: {line}")
                    try:
                        type, value = self.parse_operand_type(parts[0])
                    except Exception as e:
                        raise SyntaxError(f"Invalid CRSL syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BHH", SYMBOLS.index("<"), type.value, value
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith(">"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 1:
                        raise SyntaxError(f"Invalid CRSR syntax: {line}")
                    try:
                        type, value = self.parse_operand_type(parts[0])
                    except Exception as e:
                        raise SyntaxError(f"Invalid CRSR syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack(
                            "<BHH", SYMBOLS.index(">"), type.value, value
                        ).ljust(8, b"\x00")
                    )
                elif line.startswith("!"):
                    if len(line) != 1:
                        raise SyntaxError(f"Invalid VSYNC syntax: {line}")
                    self.instructions[bank_name].append(
                        struct.pack("<B", SYMBOLS.index("!")).ljust(8, b"\x00")
                    )
                elif line.startswith("V"):
                    parts = self.tokenize(line[1:])
                    if len(parts) != 1:
                        raise SyntaxError(f"Invalid GOSUB syntax: {line}")
                    try:
                        target = self.parse_addr(parts[0])
                    except Exception as e:
                        raise SyntaxError(f"Invalid GOSUB syntax: {line}") from e
                    self.instructions[bank_name].append(
                        struct.pack("<BH", SYMBOLS.index("V"), target).ljust(8, b"\x00")
                    )
                elif line.startswith("A"):
                    if len(line) != 1:
                        raise SyntaxError(f"Invalid RET syntax: {line}")
                    self.instructions[bank_name].append(
                        struct.pack("<B", SYMBOLS.index("A")).ljust(8, b"\x00")
                    )
                else:
                    raise SyntaxError(f"Unknown instruction: {line}")

    def parse_addr(self, token):
        if token[1:] == "_":
            return 0xF504  # CRS_REG
        elif token[1:].isdigit():
            return int(token[1:])
        elif token.startswith("$0x"):
            return int(token[3:], 16)
        elif token.startswith("$0b"):
            return int(token[3:], 2)
        elif token[1:] in self.labels:
            print(self.labels[token[1:]])
            return self.labels[token[1:]]
        elif token[1:] in self.macros:
            return self.parse_addr(self.macros[token[1:]])
        else:
            raise SyntaxError(f"Invalid address: {token}")

    def parse_operand_type(self, token):
        if token.startswith("%"):
            return self.parse_operand_type(self.macros[token[1:]])
        elif token.startswith("*"):
            return OperandType.ADDRESS, self.parse_value(token[1:])
        else:
            return OperandType.LITERAL, self.parse_value(token)

    def parse_value(self, token):
        if token.isdigit():
            return int(token)
        elif token.startswith("0x"):
            return int(token, 16)
        elif token.startswith("0b"):
            return int(token, 2)
        elif token[1:] in self.labels:
            return self.labels[token[1:]]
        elif token[1:] in self.macros:
            return self.parse_value(self.macros[token[1:]])
        else:
            raise SyntaxError(f"Invalid operand: {token}")


if __name__ == "__main__":
    assembler = Assembler(args.FILES)
    assembler.assemble()
    if "GRAPHICS" not in assembler.instructions:
        raise ValueError("Missing required GRAPHICS (CHR-ROM) bank")
    with open(args.output, "wb") as f:
        header = f"picoASM".encode("ascii")
        f.write(header)
        f.write(
            struct.pack("<B", len(assembler.instructions) - 1)
        )  # write number of banks
        graphics_bank = assembler.instructions["GRAPHICS"]
        f.write(
            struct.pack("<H", len(graphics_bank))
        )  # write size of graphics bank (in u64 instructions)
        for instr in graphics_bank:
            f.write(instr)
        for i, bank_name in enumerate(sorted(assembler.instructions.keys())):
            if bank_name == "GRAPHICS":
                continue
            f.write(struct.pack("<H", len(assembler.instructions[bank_name])))
            for instr in assembler.instructions[bank_name]:
                f.write(instr)

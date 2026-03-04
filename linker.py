from argparse import ArgumentParser

parser = ArgumentParser()

parser.add_argument("PRG_ROM", help="Path to the game program ROM binary file")
parser.add_argument("CHR_ROM", help="Path to the game character ROM data binary file")
parser.add_argument(
    "-o",
    "--output",
    help="Path to the output ROM file",
    default="output.bin",
)

parser.parse_args()

if __name__ == "__main__":
    args = parser.parse_args()
    with open(args.PRG_ROM, "rb") as prg_f:
        prg_rom_header = prg_f.read(7)
        if prg_rom_header != b"picoASM":
            raise ValueError("Invalid PRG ROM header, expected 'picoASM'")
        prg_rom = prg_f.read()

    with open(args.CHR_ROM, "rb") as chr_f:
        chr_rom_header = chr_f.read(7)
        if chr_rom_header != b"picoASM":
            raise ValueError("Invalid CHR ROM header, expected 'picoASM'")
        chr_rom = chr_f.read()

    with open(args.output, "wb") as output_f:
        output_f.write(b"picoASM")
        output_f.write(chr_rom)
        output_f.write(prg_rom)

from program import Program
from subroutine import SubRoutine
from tiles import TileSet

main_routine = SubRoutine(Program.MAIN)
# push the color green to the palette

main_routine << ("LABEL", "loop")
main_routine << ("LMOV", 0b00011100, 0xD901)  # color 2 (0b01) of palette 1
main_routine << ("LMOV", 0b00001000, 0xD803)  # FGOAM #1 attributes
main_routine << ("OUTPUT",)
main_routine << ("VSYNC",)
main_routine << ("JMP", "loop")

gfx = TileSet()

gfx.tiles[0] << 0b01010101

program = Program()
program << main_routine
program.compile("hello_world.prg")

gfx.compile("hello_world.chr")

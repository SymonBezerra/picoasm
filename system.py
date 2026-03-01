from argparse import ArgumentParser
from io import BytesIO
import os
from pathlib import Path
import struct

import pygame

from bg_oam import BackgroundOAM
from chr_rom import CharacterROM
from fg_oam import ForegroundOAM
from palette import PaletteRAM
from prg_ram import ProgramRAM
from prg_rom import ProgramROM
from stack import StackRAM
from vram import VideoRAM
from wram import WorkRAM

SCREEN_SIZE = (800, 600)
CELLS = (40, 30)
DISPLAY = pygame.display.set_mode(SCREEN_SIZE)
CLOCK = pygame.time.Clock()

parser = ArgumentParser()

parser.add_argument("FILE", help="Path to the picoASM source file")


class System:
    MEMORY_SIZE = 0xF520
    CONTROLLER_REG = 0xF500
    BANK_SWAP_REG = 0xF501
    VSYNC_REG = 0xF502

    BLOCK_H = SCREEN_SIZE[1] // (CELLS[1] * 2)
    BLOCK_W = SCREEN_SIZE[0] // (CELLS[0] * 2)

    def __init__(self, path):
        self.path = os.path.join(Path(__file__).parent, path)
        self.prg_rom = ProgramROM(self.path)
        # VRAM
        self.vram = VideoRAM()
        # CHRROM
        self.chr_rom = CharacterROM(self.path)
        # WRAM
        self.wram = WorkRAM()
        # Palettes (defined by program, not stored in ROM)
        # BGOAM
        self.bg_oam = BackgroundOAM()
        # FGOAM
        self.fg_oam = ForegroundOAM()
        # Palettes (defined by program, not stored in ROM)
        self.palette = PaletteRAM()
        # Stack RAM
        self.stack = StackRAM()
        # PRGRAM
        self.prg_ram = ProgramRAM()
        # audio channels (not implemented)

        self.controller_reg = 0x00
        self.bank_swap_reg = 0x00
        self.vsync_reg = 0x00

        self.crs = 0x0000  # Code read position
        self.pc = 0x0000  # Program counter
        self.sp = StackRAM.START_ADDR + StackRAM.STACK_SIZE - 1  # Stack pointer

        self.memory_map = [
            (
                ProgramROM.START_ADDR,
                ProgramROM.START_ADDR + ProgramROM.BANK_SIZE * 2,
                self.prg_rom.memory,
                True,  # protected (ROM)
            ),
            (
                VideoRAM.START_ADDR,
                VideoRAM.START_ADDR + VideoRAM.SIZE,
                self.vram.memory,
                False,  # not protected (RAM)
            ),
            (
                CharacterROM.START_ADDR,
                CharacterROM.START_ADDR + CharacterROM.CHRROM_SIZE,
                self.chr_rom.memory,
                True,
            ),
            (
                WorkRAM.START_ADDR,
                WorkRAM.START_ADDR + WorkRAM.WRAM_SIZE,
                self.wram.memory,
                False,
            ),
            (
                BackgroundOAM.START_ADDR,
                BackgroundOAM.START_ADDR + BackgroundOAM.OAM_SIZE,
                self.bg_oam.memory,
                False,
            ),
            (
                ForegroundOAM.START_ADDR,
                ForegroundOAM.START_ADDR + ForegroundOAM.OAM_SIZE,
                self.fg_oam.memory,
                False,
            ),
            (
                PaletteRAM.START_ADDR,
                PaletteRAM.START_ADDR + PaletteRAM.SIZE,
                self.palette.memory,
                False,
            ),
            (
                StackRAM.START_ADDR,
                StackRAM.START_ADDR + StackRAM.STACK_SIZE,
                self.stack.memory,
                False,
            ),
            (
                ProgramRAM.START_ADDR,
                ProgramRAM.START_ADDR + ProgramRAM.SIZE,
                self.prg_ram.memory,
                False,
            ),
        ]

        self.registers_map = {
            System.CONTROLLER_REG: ("controller_reg", True),
            System.BANK_SWAP_REG: ("bank_swap_reg", False),
            System.VSYNC_REG: ("vsync_reg", True),
        }

    def read_memory(self, addr):
        if addr > System.MEMORY_SIZE:
            raise ValueError(f"Address {addr:#04x} out of range")
        for start, end, memory, _ in self.memory_map:
            if start <= addr < end:
                offset = addr - start
                return memory[offset]
        for reg_addr, (reg_name, _) in self.registers_map.items():
            if addr == reg_addr:
                return getattr(self, reg_name)
        raise ValueError(f"Address {addr:#04x} is unused")

    def write_memory(self, addr, value):
        for start, end, memory, protected in self.memory_map:
            if start <= addr < end:
                if protected:
                    raise ValueError(f"Address {addr:#04x} is read-only")
                offset = addr - start
                memory[offset] = value
                return
        for reg_addr, (reg_name, protected) in self.registers_map.items():
            if addr == reg_addr:
                if protected:
                    raise ValueError(f"Address {addr:#04x} is read-only")
                setattr(self, reg_name, value)
                return
        raise ValueError(f"Address {addr:#04x} is unused")

    def run(self):
        running = True
        while self.pc < sum(self.prg_rom.banks_len) and running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            if not running:
                break
            instr = self.prg_rom.memory[
                ProgramROM.START_ADDR
                + self.pc * 8 : ProgramROM.START_ADDR
                + self.pc * 8
                + 8
            ]
            opcode = instr[0]
            if opcode == 0:  # JMP
                type = instr[1]
                operand = int.from_bytes(instr[2:4], byteorder="little")
                addr = int.from_bytes(instr[4:6], byteorder="little")
                value = None
                if type == 0:  # Immediate
                    value = operand
                elif type == 1:  # Memory
                    value = self.read_memory(addr)
                if operand:
                    self.pc = addr
            elif opcode == 1:  # ADD
                value = instr[1]
                addr = int.from_bytes(instr[2:4], byteorder="little")
                self.write_memory(addr, (self.read_memory(addr) + value) % 256)
            elif opcode == 2:  # SUB
                value = instr[1]
                addr = int.from_bytes(instr[2:4], byteorder="little")
                self.write_memory(addr, (self.read_memory(addr) - value) % 256)
            elif opcode == 3:  # MOV
                type = instr[1]
                operand = int.from_bytes(instr[2:4], byteorder="little")
                addr = int.from_bytes(instr[4:6], byteorder="little")
                value = None
                if type == 0:  # Immediate
                    value = operand
                elif type == 1:  # Memory
                    value = self.read_memory(addr)
                if value is not None:
                    self.write_memory(addr, value)
            elif opcode == 4:  # CGTZ
                addr1 = int.from_bytes(instr[1:3], byteorder="little")
                addr2 = int.from_bytes(instr[3:5], byteorder="little")
                self.write_memory(addr2, 1 if self.read_memory(addr1) > 0 else 0)
            elif opcode == 5:  # CEQ
                addr1 = int.from_bytes(instr[1:3], byteorder="little")
                addr2 = int.from_bytes(instr[3:5], byteorder="little")
                addr3 = int.from_bytes(instr[5:7], byteorder="little")
                self.write_memory(
                    addr3,
                    1 if self.read_memory(addr1) == self.read_memory(addr2) else 0,
                )
            elif opcode == 6:  # RET
                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    running = False
                elif keys[pygame.K_i]:  # up
                    self.controller_reg |= 1
                elif keys[pygame.K_k]:  # down
                    self.controller_reg |= 1 << 1
                elif keys[pygame.K_j]:  # left
                    self.controller_reg |= 1 << 2
                elif keys[pygame.K_l]:  # right
                    self.controller_reg |= 1 << 3
                elif keys[pygame.K_z]:  # B
                    self.controller_reg |= 1 << 4
                elif keys[pygame.K_x]:  # A
                    self.controller_reg |= 1 << 5
                elif keys[pygame.K_SPACE]:  # Select
                    self.controller_reg |= 1 << 6
                elif keys[pygame.K_RETURN]:  # Start
                    self.controller_reg |= 1 << 7
            elif opcode == 7:  # OUT
                self.output_video()
            elif opcode == 8:  # CRSJ
                addr = int.from_bytes(instr[1:3], byteorder="little")
                self.crs = addr
            elif opcode == 10:  # CRSL
                value = instr[1]
                self.crs = (self.crs - value) % 65536
            elif opcode == 11:  # CRSR
                value = instr[1]
                self.crs = (self.crs + value) % 65536
            elif opcode == 12:  # VSYNC
                self.vsync_reg = 1 if CLOCK.tick(60) > 1000 else 0
            elif opcode == 13:  # GOSUB
                addr = int.from_bytes(instr[1:3], byteorder="little")
                self.write_memory(self.sp, (self.pc + 1) & 0xFF)
                self.write_memory(self.sp - 1, ((self.pc + 1) >> 8) & 0xFF)
                self.sp -= 2
                self.pc = addr - 1
            elif opcode == 14:  # RET
                self.sp += 2
                self.pc = (self.read_memory(self.sp - 1) << 8) | self.read_memory(
                    self.sp - 2
                )
            else:
                raise ValueError(f"Unknown opcode: {opcode}")
            self.pc += 1
            # if self.bank_swap_reg:
            #     self.swap_banks()
        pygame.quit()

    def output_video(self):
        # 2x2 pixel blocks, 4 bytes per block, 8 bytes per tile, 512 tiles total (4KB VRAM)
        bg_surface0 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        bg_surface1 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for obj_index in range(BackgroundOAM.OAM_SIZE):
            # OAM: [hi, lo, palette, attributes]
            oam_base = obj_index * 4
            oam_data = self.bg_oam[oam_base : oam_base + 4]
            palette = oam_data[2]
            attributes = oam_data[3]

            if not (attributes & (1 << 3)):  # bit 3 = visible
                continue
            vflip = bool(attributes & 1)
            hflip = bool(attributes & 1 << 1)
            priority = bool(attributes & 1 << 2)
            target_surface = bg_surface1 if priority else bg_surface0
            monochrome = bool(attributes & 1 << 4)
            animation_offset = (attributes >> 5) & 0b111
            vram_hibyte = oam_data[0]
            vram_lobyte = oam_data[1]
            tile_index = (vram_hibyte << 8) | vram_lobyte

            # VRAM: [hi, lo, x_screen, y_screen]
            vram_base = tile_index * 4
            vram_data = self.vram[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            chr_data = self.chr_rom[tile_index]
            for py in range(2):
                for px in range(2):
                    sub = py * 2 + px

                    # Apply flips when sampling CHR data
                    sample_px = (1 - px) if hflip else px
                    sample_py = (1 - py) if vflip else py
                    sample_sub = sample_py * 2 + sample_px

                    pixel_bits = (chr_data >> (6 - sample_sub * 2)) & 0x03
                    if monochrome and pixel_bits != 0:
                        pixel_bits = 1
                    color = self.palette[palette * 4 + pixel_bits]
                    rgb = System.rgb_transform(color)
                    pygame.draw.rect(
                        target_surface,
                        rgb,
                        (
                            tile_x * (SCREEN_SIZE[0] // CELLS[0])
                            + px * (SCREEN_SIZE[0] // (CELLS[0] * 2)),
                            tile_y * (SCREEN_SIZE[1] // CELLS[1])
                            + py * (SCREEN_SIZE[1] // (CELLS[1] * 2)),
                            System.BLOCK_W,
                            System.BLOCK_H,
                        ),
                    )
        DISPLAY.blit(bg_surface0, (0, 0))
        DISPLAY.blit(bg_surface1, (0, 0))

        fg_surface0 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        fg_surface1 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for obj_index in range(ForegroundOAM.OAM_SIZE):
            # OAM: [hi, lo, palette, attributes]
            oam_base = obj_index * 4
            oam_data = self.memory[oam_base : oam_base + 4]
            palette = oam_data[2]
            attributes = oam_data[3]

            if not (attributes & (1 << 3)):  # bit 3 = visible
                continue
            vflip = bool(attributes & 1)
            hflip = bool(attributes & 1 << 1)
            priority = bool(attributes & 1 << 2)
            target_surface = fg_surface1 if priority else fg_surface0
            monochrome = bool(attributes & 1 << 4)
            animation_offset = (attributes >> 5) & 0b111
            vram_hibyte = oam_data[0]
            vram_lobyte = oam_data[1]
            tile_index = (vram_hibyte << 8) | vram_lobyte

            # VRAM: [hi, lo, x_screen, y_screen]
            vram_base = tile_index * 4
            vram_data = self.memory[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            # CHR-ROM: 8 bytes per tile
            chr_data = self.chr_rom[tile_index]
            for py in range(2):
                for px in range(2):
                    sub = py * 2 + px

                    # Apply flips when sampling CHR data
                    sample_px = (1 - px) if hflip else px
                    sample_py = (1 - py) if vflip else py
                    sample_sub = sample_py * 2 + sample_px

                    pixel_bits = (chr_data >> (6 - sample_sub * 2)) & 0x03
                    if monochrome and pixel_bits != 0:
                        pixel_bits = 1
                    color = self.palette[palette * 4 + pixel_bits]
                    rgb = System.rgb_transform(color)
                    pygame.draw.rect(
                        target_surface,
                        rgb,
                        (
                            tile_x * (SCREEN_SIZE[0] // CELLS[0])
                            + px * (SCREEN_SIZE[0] // (CELLS[0] * 2)),
                            tile_y * (SCREEN_SIZE[1] // CELLS[1])
                            + py * (SCREEN_SIZE[1] // (CELLS[1] * 2)),
                            System.BLOCK_W,
                            System.BLOCK_H,
                        ),
                    )

        DISPLAY.blit(fg_surface0, (0, 0))
        DISPLAY.blit(fg_surface1, (0, 0))
        pygame.display.flip()

    @staticmethod
    def rgb_transform(color):
        r = (color >> 5) & 0x07
        g = (color >> 2) & 0x07
        b = (color >> 0) & 0x03

        # scale to 8-bit per channel
        r = (r << 5) | (r << 2) | (r >> 1)  # 3-bit → 8-bit
        g = (g << 5) | (g << 2) | (g >> 1)  # 3-bit → 8-bit
        b = (b << 6) | (b << 4) | (b << 2) | b  # 2-bit → 8-bit

        return (r, g, b)

    def swap_banks(self):
        def read(fmt):
            size = struct.calcsize(fmt)
            data = self.bytes.read(size)
            if not data:
                raise EOFError("End of file reached")
            return struct.unpack(fmt, data)[0]

        with open(Path(os.path.join(os.getcwd(), self.path)), "rb") as f:
            self.bytes = BytesIO(f.read())
        # skip header and bank lengths
        self.bytes.seek(8)
        # read the new bank data
        for _ in range(self.bank_swap_reg - 1):
            size = read("<H")  # skip size of previous banks
            self.bytes.seek(size * 8, 1)  # skip previous bank data
        bank_size = read("<H")  # Read the size of the bank
        bank_data = [
            read("<Q") for _ in range(bank_size)
        ]  # Read the instructions as 64-bit values
        rom = b"".join(instr.to_bytes(8, "little") for instr in bank_data)

        start = ProgramROM.PRGROM_BANKS[1]
        end = start + len(rom)

        max_end = ProgramROM.PRGROM_BANKS[1] + ProgramROM.BANK_SIZE

        if end > max_end:
            rom = rom[: max_end - start]  # truncate like real hardware

        self.prg_rom.memory[start : start + len(rom)] = rom
        self.prg_rom.swap_bank = 0  # reset the bank swap flag


if __name__ == "__main__":
    args = parser.parse_args()
    console = System(args.FILE)
    console.run()

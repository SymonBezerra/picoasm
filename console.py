from argparse import ArgumentParser
from io import BytesIO
import os
from pathlib import Path
import struct

import pygame

SCREEN_SIZE = (800, 600)
CELLS = (40, 30)
DISPLAY = pygame.display.set_mode(SCREEN_SIZE)
CLOCK = pygame.time.Clock()

parser = ArgumentParser()

parser.add_argument("FILE", help="Path to the picoASM source file")


class Console:
    CONTROLLER = 0xF900
    BANK_SWAP = 0xF901
    VSYNC = 0xF902

    PRGROM_BANKS = (0x0000, 0x4000)
    PRGROM_BANK_SIZE = 0x4000

    VRAM_START = 0x8000
    CHRROM_START = 0x9000
    BG_OAM_START = 0xD000
    FG_OAM_START = 0xD800
    PAL_START = 0xD900

    BG_OAM_SIZE = 512
    FG_OAM_SIZE = 128

    BLOCK_H = SCREEN_SIZE[1] // (CELLS[1] * 2)
    BLOCK_W = SCREEN_SIZE[0] // (CELLS[0] * 2)

    def __init__(self, path):
        self.path = path
        with open(Path(os.path.join(os.getcwd(), self.path)), "rb") as f:
            self.bytes = BytesIO(f.read())

        # read the magic header "picoASM"
        header = self.bytes.read(7)
        if header != b"picoASM":
            raise ValueError("Invalid file format: missing magic header")
        self.banks_count = self.read("<B")  # Read the number of banks
        self.banks_len = []
        self.memory = bytearray(0xF520)  # approximately 64KB of memory
        for i in range(min(self.banks_count, 2)):  # Only read up to 2 banks
            bank_size = self.read("<H")  # Read the size of the bank
            self.banks_len.append(bank_size)
            start = Console.PRGROM_BANKS[i]
            bank_data = [
                self.read("<Q") for _ in range(bank_size)
            ]  # Read the instructions as 64-bit values
            rom = b"".join(instr.to_bytes(8, "little") for instr in bank_data)

            start = Console.PRGROM_BANKS[i]
            end = start + len(rom)

            max_end = Console.PRGROM_BANKS[i] + Console.PRGROM_BANK_SIZE

            if end > max_end:
                rom = rom[: max_end - start]  # truncate like real hardware

            self.memory[start : start + len(rom)] = rom

        self.pc = 0
        self.sp = 0xDBFF  # Stack pointer starts at the end of memory
        self.swap_bank = 1  # Start with bank 0 active, and bank 1 as the swap bank
        self.crs = 0  # Cursor (BF inspired)

    def read(self, fmt):
        size = struct.calcsize(fmt)
        data = self.bytes.read(size)
        if not data:
            raise EOFError("End of file reached")
        return struct.unpack(fmt, data)[0]

    def run(self):
        bank = 0
        running = True
        while self.pc < sum(self.banks_len) and running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            if not running:
                break
            instr = self.memory[
                Console.PRGROM_BANKS[bank]
                + self.pc * 8 : Console.PRGROM_BANKS[bank]
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
                    value = self.memory[addr]
                if operand:
                    self.pc = addr
            elif opcode == 1:  # ADD
                value = instr[1]
                addr = int.from_bytes(instr[2:4], byteorder="little")
                self.memory[addr] = (self.memory[addr] + value) % 256
            elif opcode == 2:  # SUB
                value = instr[1]
                addr = int.from_bytes(instr[2:4], byteorder="little")
                self.memory[addr] = (self.memory[addr] - value) % 256
            elif opcode == 3:  # MOV
                type = instr[1]
                operand = int.from_bytes(instr[2:4], byteorder="little")
                addr = int.from_bytes(instr[4:6], byteorder="little")
                value = None
                if type == 0:  # Immediate
                    value = operand
                elif type == 1:  # Memory
                    value = self.memory[addr]
                if value is not None:
                    self.memory[addr] = value
            elif opcode == 4:  # CGTZ
                addr1 = int.from_bytes(instr[1:3], byteorder="little")
                addr2 = int.from_bytes(instr[3:5], byteorder="little")
                self.memory[addr2] = 1 if self.memory[addr1] > 0 else 0
            elif opcode == 5:  # CEQ
                addr1 = int.from_bytes(instr[1:3], byteorder="little")
                addr2 = int.from_bytes(instr[3:5], byteorder="little")
                addr3 = int.from_bytes(instr[5:7], byteorder="little")
                self.memory[addr3] = (
                    1 if self.memory[addr1] == self.memory[addr2] else 0
                )
            elif opcode == 6:  # RET
                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    running = False
                elif keys[pygame.K_i]:  # up
                    self.memory[Console.CONTROLLER] |= 1
                elif keys[pygame.K_k]:  # down
                    self.memory[Console.CONTROLLER] |= 1 << 1
                elif keys[pygame.K_j]:  # left
                    self.memory[Console.CONTROLLER] |= 1 << 2
                elif keys[pygame.K_l]:  # right
                    self.memory[Console.CONTROLLER] |= 1 << 3
                elif keys[pygame.K_z]:  # B
                    self.memory[Console.CONTROLLER] |= 1 << 4
                elif keys[pygame.K_x]:  # A
                    self.memory[Console.CONTROLLER] |= 1 << 5
                elif keys[pygame.K_SPACE]:  # Select
                    self.memory[Console.CONTROLLER] |= 1 << 6
                elif keys[pygame.K_RETURN]:  # Start
                    self.memory[Console.CONTROLLER] |= 1 << 7
            elif opcode == 7:  # OUT
                self.output_video()
            elif opcode == 8:  # CRSJ
                addr = int.from_bytes(instr[1:3], byteorder="little")
                self.crs = self.memory[addr]
            elif opcode == 10:  # CRSL
                value = instr[1]
                self.crs = (self.crs - value) % 65536
            elif opcode == 11:  # CRSR
                value = instr[1]
                self.crs = (self.crs + value) % 65536
            elif opcode == 12:  # VSYNC
                self.memory[Console.VSYNC] = 1 if CLOCK.tick(60) > 1000 else 0
            elif opcode == 13:  # GOSUB
                addr = int.from_bytes(instr[1:3], byteorder="little")
                self.memory[self.sp] = (self.pc + 1) & 0xFF
                self.memory[self.sp - 1] = ((self.pc + 1) >> 8) & 0xFF
                self.sp -= 2
                self.pc = addr - 1
            elif opcode == 14:  # RET
                self.sp += 2
                self.pc = (self.memory[self.sp - 1] << 8) | self.memory[self.sp - 2]
            else:
                raise ValueError(f"Unknown opcode: {opcode}")
            self.pc += 1
            if self.memory[Console.BANK_SWAP]:
                self.swap_banks()
        pygame.quit()

    def output_video(self):
        # 2x2 pixel blocks, 4 bytes per block, 8 bytes per tile, 512 tiles total (4KB VRAM)
        bg_surface0 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        bg_surface1 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for obj_index in range(Console.BG_OAM_SIZE):
            # OAM: [hi, lo, palette, attributes]
            oam_base = Console.BG_OAM_START + obj_index * 4
            oam_data = self.memory[oam_base : oam_base + 4]
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
            vram_base = Console.VRAM_START + tile_index * 4
            vram_data = self.memory[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            # CHR-ROM: 8 bytes per tile
            chr_base = Console.CHRROM_START + tile_index
            chr_data = self.memory[chr_base]
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
                    color = self.memory[Console.PAL_START + palette * 4 + pixel_bits]
                    rgb = Console.rgb_transform(color)
                    pygame.draw.rect(
                        target_surface,
                        rgb,
                        (
                            tile_x * (SCREEN_SIZE[0] // CELLS[0])
                            + px * (SCREEN_SIZE[0] // (CELLS[0] * 2)),
                            tile_y * (SCREEN_SIZE[1] // CELLS[1])
                            + py * (SCREEN_SIZE[1] // (CELLS[1] * 2)),
                            Console.BLOCK_W,
                            Console.BLOCK_H,
                        ),
                    )
        DISPLAY.blit(bg_surface0, (0, 0))
        DISPLAY.blit(bg_surface1, (0, 0))

        fg_surface0 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        fg_surface1 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for obj_index in range(Console.FG_OAM_SIZE):
            # OAM: [hi, lo, palette, attributes]
            oam_base = Console.FG_OAM_START + obj_index * 4
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
            vram_base = Console.VRAM_START + tile_index * 4
            vram_data = self.memory[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            # CHR-ROM: 8 bytes per tile
            chr_base = Console.CHRROM_START + tile_index
            chr_data = self.memory[chr_base]
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
                    color = self.memory[Console.PAL_START + palette * 4 + pixel_bits]
                    rgb = Console.rgb_transform(color)
                    pygame.draw.rect(
                        target_surface,
                        rgb,
                        (
                            tile_x * (SCREEN_SIZE[0] // CELLS[0])
                            + px * (SCREEN_SIZE[0] // (CELLS[0] * 2)),
                            tile_y * (SCREEN_SIZE[1] // CELLS[1])
                            + py * (SCREEN_SIZE[1] // (CELLS[1] * 2)),
                            Console.BLOCK_W,
                            Console.BLOCK_H,
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
        with open(Path(os.path.join(os.getcwd(), self.path)), "rb") as f:
            self.bytes = BytesIO(f.read())
        # skip header and bank lengths
        self.bytes.seek(7 + 1 + self.banks_count * 2)
        # read the new bank data
        bank_size = self.read("<H")  # Read the size of the bank
        bank_data = [
            self.read("<Q") for _ in range(bank_size)
        ]  # Read the instructions as 64-bit values
        rom = b"".join(instr.to_bytes(8, "little") for instr in bank_data)

        start = Console.PRGROM_BANKS[1]
        end = start + len(rom)

        max_end = Console.PRGROM_BANKS[1] + Console.PRGROM_BANK_SIZE

        if end > max_end:
            rom = rom[: max_end - start]  # truncate like real hardware

        self.memory[start : start + len(rom)] = rom
        self.memory[Console.BANK_SWAP] = 0  # reset the bank swap flag


if __name__ == "__main__":
    args = parser.parse_args()
    console = Console(args.FILE)
    console.run()

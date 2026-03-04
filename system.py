from argparse import ArgumentParser
import os
from pathlib import Path

import pygame

from bg_oam import BackgroundOAM
from chr_rom import CharacterROM
from fg_oam import ForegroundOAM
from opcodes import OPCODES
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
    PRGRAM_SAVE_REG = 0xF503

    BLOCK_H = SCREEN_SIZE[1] // (CELLS[1] * 2)
    BLOCK_W = SCREEN_SIZE[0] // (CELLS[0] * 2)

    def __init__(self, path):
        self.path = os.path.join(Path(__file__).parent, path)
        self.prg_rom = ProgramROM()
        # VRAM
        self.vram = VideoRAM()
        # CHRROM
        self.chr_rom = CharacterROM()
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
        self.prgram_save_reg = 0x00

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
            System.VSYNC_REG: ("vsync_reg", False),
            System.PRGRAM_SAVE_REG: ("prgram_save_reg", False),
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
        while running:
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
            self.execute_instr(instr)
            if self.pc < len(self.prg_rom.memory) // 8 - 1:
                self.pc += 1
            if self.prgram_save_reg:
                with open(self.path.replace(".bin", "_save.bin"), "wb") as f:
                    f.write(self.prg_ram.memory)
                self.prgram_save_reg = 0
        pygame.quit()

    def execute_instr(self, instr):
        opcode = instr[0]
        if opcode == OPCODES["NOP"][0]:  # NOP
            return
        if opcode == OPCODES["JMP"][0]:  # JMP
            target = int.from_bytes(instr[1:3], byteorder="little")
            self.pc = target - 1  # -1 because we'll increment after execution
        elif opcode == OPCODES["ADD"][0]:  # ADD
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = (self.read_memory(addr1) + self.read_memory(addr2)) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["ADD_X"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) + self.x) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["ADD_Y"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) + self.y) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["ADD_A"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) + self.a) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["SUB"][0]:  # SUB
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = (self.read_memory(addr1) - self.read_memory(addr2)) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["SUB_X"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) - self.x) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["SUB_Y"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) - self.y) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["SUB_A"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) - self.a) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MULT"][0]:  # MULT
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = (self.read_memory(addr1) * self.read_memory(addr2)) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MULT_X"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) * self.x) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MULT_Y"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) * self.y) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MULT_A"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (self.read_memory(addr) * self.a) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["DIV"][0]:  # DIV
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            divisor = self.read_memory(addr2)
            value = (self.read_memory(addr1) // divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["DIV_X"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.x
            value = (self.read_memory(addr) // divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["DIV_Y"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.y
            value = (self.read_memory(addr) // divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["DIV_A"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.a
            value = (self.read_memory(addr) // divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOD"][0]:  # MOD
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            divisor = self.read_memory(addr2)
            value = (self.read_memory(addr1) % divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOD_X"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.x
            value = (self.read_memory(addr) % divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOD_Y"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.y
            value = (self.read_memory(addr) % divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOD_A"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            divisor = self.a
            value = (self.read_memory(addr) % divisor) & 0xFF if divisor != 0 else 0
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["LSHIFT"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            shift_amount = instr[3]
            value = (self.read_memory(addr) << shift_amount) & 0xFF
            self.write_memory(addr, value)
        elif opcode == OPCODES["LSHIFT_X"]:
            shift_amount = instr[1]
            self.x = (self.x << shift_amount) & 0xFF
        elif opcode == OPCODES["LSHIFT_Y"]:
            shift_amount = instr[1]
            self.y = (self.y << shift_amount) & 0xFF
        elif opcode == OPCODES["LSHIFT_A"]:
            shift_amount = instr[1]
            self.a = (self.a << shift_amount) & 0xFF
        elif opcode == OPCODES["RSHIFT"]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            shift_amount = instr[3]
            value = (self.read_memory(addr) >> shift_amount) & 0xFF
            self.write_memory(addr, value)
        elif opcode == OPCODES["RSHIFT_X"]:
            shift_amount = instr[1]
            self.x = (self.x >> shift_amount) & 0xFF
        elif opcode == OPCODES["RSHIFT_Y"]:
            shift_amount = instr[1]
            self.y = (self.y >> shift_amount) & 0xFF
        elif opcode == OPCODES["RSHIFT_A"]:
            shift_amount = instr[1]
            self.a = (self.a >> shift_amount) & 0xFF
        elif opcode == OPCODES["AND"][0]:  # AND
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = self.read_memory(addr1) & self.read_memory(addr2)
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["AND_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) & self.x
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["AND_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) & self.y
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["AND_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) & self.a
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["OR"][0]:
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = self.read_memory(addr1) | self.read_memory(addr2)
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["OR_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) | self.x
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["OR_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) | self.y
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["OR_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) | self.a
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["NOT"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = (~self.read_memory(addr)) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["NOT_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = (~self.read_memory(addr)) & 0xFF
            self.x = value
        elif opcode == OPCODES["NOT_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = (~self.read_memory(addr)) & 0xFF
            self.y = value
        elif opcode == OPCODES["NOT_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = (~self.read_memory(addr)) & 0xFF
            self.a = value
        elif opcode == OPCODES["XOR"][0]:
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = self.read_memory(addr1) ^ self.read_memory(addr2)
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XOR_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) ^ self.x
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XOR_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) ^ self.y
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XOR_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr) ^ self.a
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XNOR"][0]:
            addr1 = int.from_bytes(instr[1:3], byteorder="little")
            addr2 = int.from_bytes(instr[3:5], byteorder="little")
            target_addr = int.from_bytes(instr[5:7], byteorder="little")
            value = ~(self.read_memory(addr1) ^ self.read_memory(addr2)) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XNOR_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = ~(self.read_memory(addr) ^ self.x) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XNOR_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = ~(self.read_memory(addr) ^ self.y) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["XNOR_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = ~(self.read_memory(addr) ^ self.a) & 0xFF
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOV"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            target_addr = int.from_bytes(instr[3:5], byteorder="little")
            value = self.read_memory(addr)
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["MOV_X"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = self.read_memory(addr)
            self.x = value
        elif opcode == OPCODES["MOV_Y"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = self.read_memory(addr)
            self.y = value
        elif opcode == OPCODES["MOV_A"][0]:
            addr = int.from_bytes(instr[1:3], byteorder="little")
            value = self.read_memory(addr)
            self.a = value
        elif opcode == OPCODES["LMOV"][0]:
            value = instr[1]
            target_addr = int.from_bytes(instr[2:4], byteorder="little")
            self.write_memory(target_addr, value)
        elif opcode == OPCODES["LMOV_X"][0]:
            value = instr[1]
            self.x = value
        elif opcode == OPCODES["LMOV_Y"][0]:
            value = instr[1]
            self.y = value
        elif opcode == OPCODES["LMOV_A"][0]:
            value = instr[1]
            self.a = value
        elif opcode == OPCODES["INPUT"][0]:
            keys = pygame.key.get_pressed()
            controller_state = 0
            if keys[pygame.K_i]:  # up
                controller_state |= 1
            if keys[pygame.K_k]:  # down
                controller_state |= 1 << 1
            if keys[pygame.K_j]:  # left
                controller_state |= 1 << 2
            if keys[pygame.K_l]:  # right
                controller_state |= 1 << 3
            if keys[pygame.K_z]:  # B
                controller_state |= 1 << 4
            if keys[pygame.K_x]:  # A
                controller_state |= 1 << 5
            if keys[pygame.K_SPACE]:  # Select
                controller_state |= 1 << 6
            if keys[pygame.K_RETURN]:  # Start
                controller_state |= 1 << 7
            self.write_memory(System.CONTROLLER_REG, controller_state)
        elif opcode == OPCODES["OUTPUT"][0]:
            self.output_video()
        elif opcode == OPCODES["VSYNC"][0]:
            vsync_flag = CLOCK.tick(60) > 1000
            self.write_memory(System.VSYNC_REG, 1 if vsync_flag else 0)
        elif opcode == OPCODES["GOSUB"][0]:
            lo_byte = instr[1]
            hi_byte = instr[2]
            target = (hi_byte << 8) | lo_byte
            pc_hibyte = (self.pc + 1) >> 8
            pc_lobyte = (self.pc + 1) & 0xFF
            self.stack.memory[self.sp] = pc_hibyte
            self.sp -= 1
            self.stack.memory[self.sp] = pc_lobyte
            self.sp -= 1
            self.pc = target - 1  # -1 because we'll increment after execution
        elif opcode == OPCODES["RET"][0]:
            self.sp += 1
            pc_lobyte = self.stack.memory[self.sp]
            self.sp += 1
            pc_hibyte = self.stack.memory[self.sp]
            self.pc = (
                (pc_hibyte << 8) | pc_lobyte
            ) - 1  # -1 because we'll increment after execution
        elif opcode == OPCODES["LABEL"][0]:
            return  # no operation needed for labels at runtime
        else:
            raise ValueError(f"Unknown opcode {opcode:#02x} at PC {self.pc:#04x}")

    def output_video(self):
        # 2x2 pixel blocks, 4 bytes per block, 8 bytes per tile, 512 tiles total (4KB VRAM)
        bg_surface0 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        bg_surface1 = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for obj_index in range(BackgroundOAM.OAM_SIZE):
            # OAM: [hi, lo, palette, attributes]
            oam_base = obj_index * 4
            oam_data = self.bg_oam.memory[oam_base : oam_base + 4]
            if not any(oam_data):
                continue
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
            vram_data = self.vram.memory[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            chr_data = self.chr_rom.memory[tile_index]
            for py in range(2):
                for px in range(2):
                    sub = py * 2 + px

                    # Apply flips when sampling CHR data
                    sample_px = (1 - px) if hflip else px
                    sample_py = (1 - py) if vflip else py
                    sample_sub = sample_py * 2 + sample_px

                    pixel_bits = (chr_data >> (6 - sample_sub * 2)) & 0b11
                    if monochrome and pixel_bits != 0:
                        pixel_bits = 1
                    color = self.palette.memory[palette * 4 + pixel_bits]
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
            oam_data = self.fg_oam.memory[oam_base : oam_base + 4]
            if not any(oam_data):
                continue
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
            vram_data = self.vram.memory[vram_base : vram_base + 4]
            tile_x = vram_data[2]
            tile_y = vram_data[3]
            chr_data = self.chr_rom.memory[tile_index]
            for py in range(2):
                for px in range(2):

                    sample_px = (1 - px) if hflip else px
                    sample_py = (1 - py) if vflip else py
                    sample_sub = sample_py * 2 + sample_px

                    pixel_bits = (chr_data >> (6 - sample_sub * 2)) & 0x03
                    if monochrome and pixel_bits != 0:
                        pixel_bits = 1
                    color = self.palette.memory[palette * 4 + pixel_bits]
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
        DISPLAY.blit(fg_surface0, (0, 0))
        DISPLAY.blit(bg_surface1, (0, 0))
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

    def load_rom(self):
        with open(self.path, "rb") as f:
            header = f.read(7)
            if header != b"picoASM":
                raise ValueError("Invalid ROM header, expected 'picoASM'")
            chr_len = int.from_bytes(f.read(2), byteorder="little")
            chr_data = f.read(chr_len)
            # read directly into CHR ROM memory, without casting to int
            self.chr_rom.memory[:chr_len] = chr_data
            prg_rom_entrypoint = int.from_bytes(f.read(2), byteorder="little")
            self.pc = prg_rom_entrypoint
            prg_rom = f.read()
            # read directly into PRG ROM memory, without casting to int
            self.prg_rom.memory[: len(prg_rom)] = prg_rom


if __name__ == "__main__":
    args = parser.parse_args()
    console = System(args.FILE)
    console.load_rom()
    console.run()

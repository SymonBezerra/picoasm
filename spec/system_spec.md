# picoASM System Spec

- inspired on Game Boy's architecture (no separate PPU and CPU)

- approximately 64KB address space (16 bit addressing)

- Registers: PC, SP, CRS (BF Cursor)

## Memory Map

- 0x0000 → 0x3FFF → 16KB PRG-ROM Bank 0
- 0x4000 → 0x7FFF → 16KB PRG-ROM Bank 1 (Switchable)
- 0x8000 → 0x8FFF → 4KB VRAM
    + `[hi-byte] [lo-byte] [x coordinate] [y coordinate]`
    + attributes (from LSB to MSB)
        - bit 0: v-flip
        - bit 1: h-flip
        - bit 2: priority
        - bit 3: hidden
        - bit 4: monochrome
        - bit 5-7: animation offset
    + 8192 bytes / 4 → 2048 tiles in VRAM
- 0x9000 → 0xAFFF → 16KB CHR-ROM
    + each byte is a 2x2 pixel grid
    + each 8 bytes is a 16x16 grid
- 0xB000 → 0xBFFF → 4KB WRAM
- 0xC000 → 0xCFFF → 4KB WRAM

- 0xD000 → 0xD7FF → 2KB Object Attribute Mapper (Background)
    + 512 objects on background
- 0xD800 → 0xD8FF → 256B Object Attribute Mapper (Foreground)
    + 64 objects on foreground
- 0xD900 → 0xDCFF → Color Palettes (1KB)
- 0xDD00 → 0xE4FF → Stack RAM (2KB, reserved)
    → enough to create a stack of length 1024
- E500 → F4FF → PRG-RAM (battery backed, 4KB)
- F500 → F50F → I\O
    + F500 → Controller
    + F501 → Bank swap
    + F502 → V-Sync flag (keep it?)
- F510 → F51F → Audio channels

- display is 32x24 (640x480)
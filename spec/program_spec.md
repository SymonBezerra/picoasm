# Program Spec

- instruction (8 bytes) → 16KB / 8 → 2048 lines per program bank
    + `[JMP "@" (0)] [operand type(u8), address or literal] [operand (u16)] [address (u16)]`
    + `[ADD "+" (1)] [value (u8)] [address (u16)]`
    + `[SUB "-" (2)] [value (u8)] [address (u16)]`
    + `[MOV "#" (3)] [operand type(u8), ADDRESS_CONTENT or LITERAL] [operand (u16), address or 8-bit value] [address (u16)]`
    + `[CGTZ "?" (4)] [address (u16)] [address (u16)]`
    + `[CEQ "=" (5)] [address (u16)] [address (u16)] [address (u16)]`
    + `[INP "," (6)]`
    + `[OUT "." (7)"]`
    + `[CRSJ "^" (8)] [address (u16)]`
    + `[CRSL "<" (10)] [value (u8)]`
    + `[CRSR ">" (11)] [value (u8)]`
    + `[VSYNC "!" (12)]`
    + `[GOSUB "V" (13)] [address (u16)]`
    + `[RET "A" (14)]`

- PRG-ROM Banks
    + switchable bank is to be controlled via I\O Register
    + default banks are to be 0 and 1
    + `TODO` → insert a limit of 8 banks

- no address is relative
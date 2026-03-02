# picoASM - Small 8-bit Virtual Assembly Language

- all memory values are `uint8_t` (0-255)

- `<<` → bitwise shift left
- `>>` → bitwise shift right
- `&` → bitwise AND
- `|` → bitwise OR
- `~` → bitwise NOT


- `$` → address specifier

- `:` → label specifier

- `;` → comment specifier

- `*` → dereference

- `!` → tells if a full frame has passed (V-Sync routine)

- `%` → macro specifier
  + `%STACK_POINTER $256` → interpreter substitutes `STACK_POINTER` symbol for `#256`

- `@ [value] [label]` → goto (conditional)
    + `@ *256 :marker` → if $256 > 0, goto line of `marker`
	+ `@ 1 :marker` → unconditional goto
	
- `= [addr 1] [addr 2] [save addr]` → equality comparison
  + `= $256 $257 $258` → compare $256 to $257, if true push 1 to $$258, else push 0
  
- `? [addr] [ save addr]` → compare if greater than zero
  + `? $256 $257` → compare if the value of $256 is greater than zero, and push result to $257

- `# [value] [addr]` → push bitwise value to address
    + `$ *257 $256` → push value of $257 to $256

- `,` → get user input
- `.` → output VRAM

- `+ [value] [addr]` → addition
  + `+ *256 $257` → add value of $256 to $257
  
- `- [value] [addr]` → subtraction

- `^` → jump cursor to address
- `> [int]` → shift cursor to the left
- `< [int]` → shift cursor to the right

- `_` → get value of cursor's position

- `V [label]` → go subrotine
- `A` → return from subroutine

- `{ section name }`

- `{{ include picoASM file }}`

## Notes about the picoASM Language

- bitwise operations are not inplace
  + `+ *1 << 2 #2` → shifts value of `#1` two bits to the right,
  but **DOES NOT** change the value inside `#1`
  
  + `$ *1 | 0b11 << 2 #1` → makes a bitwise operation,
  and pushes the value inside `#2`

  + `0x` and `0b` are supported

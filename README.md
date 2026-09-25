# 8-Bit CPU

A microcoded 8-bit CPU built from 24 74HC-series logic and memory ICs: custom
instruction set, 4 general-purpose registers, add/subtract ALU with Zero and
Carry flags, and a control unit driven entirely by two EEPROMs.

<img width="960" height="200" alt="image" src="https://github.com/user-attachments/assets/d5882a13-a494-495a-a691-610ce441e075" />
*Preview from JLCPCB

## Status: In progress

- [x] Instruction set (10 instructions, 1- and 2-byte encodings)
- [x] Microcode ROM generator (`ROM/microcode_rom_gen.py`)
- [x] Emulator + assembler, full test program passing
- [x] Schematic: 24 ICs, generated from one netlist table
      (`kicad_files/gen_schematic.py`), 0 ERC errors
- [x] Schematic verified by simulation: the KiCad netlist runs the test program
      at the chip-pin level with the real ROM images (`kicad_files/sim_netlist.py`)
- [x] PCB: 2-layer, 160 × 140 mm, fully routed (Freerouting), GND pour on
      both layers; DRC clean (0 errors, 0 warnings, 0 unconnected) and 0
      schematic-parity differences
- [x] Fabrication outputs: Gerbers + drill (`fab/8-bit-cpu-gerbers.zip`),
      BOM and pick-and-place files
- [ ] Order boards, burn the EEPROMs, and bring up the hardware

## Overview

| | |
|---|---|
| Data path | 8-bit |
| Registers | R0–R3 (2 × 74HC670 register file), plus PC, MAR, IR, A, TEMP |
| Control unit | Microcoded: 2 × 28C256, addressed by opcode, 2-bit step, Z, C |
| ALU | Add, subtract (two's complement), Zero and Carry flags |
| Memory | Harvard: 256 B program EEPROM (28C64), 256 B data SRAM (6116) |
| Clock | 1 MHz canned oscillator (target 1–2 MHz), or external via jumper |
| IC count | 24 (+ oscillator) |
| Board | 2-layer, 160 × 140 mm, SMD logic; EEPROMs and SRAM in DIP sockets so they can be reprogrammed |
| Power | USB-C, 5 V, polyfuse |

## Instruction Set

| Opcode | Mnemonic | Bytes | Operation |
|---|---|---|---|
| `0000` | `NOP` | 1 | No operation |
| `0001` | `LOAD Rd, addr` | 2 | Rd ← RAM[addr] |
| `0010` | `STORE Rd, addr` | 2 | RAM[addr] ← Rd |
| `0011` | `ADD Rd, Rs` | 1 | Rd ← Rd + Rs (sets Z, C) |
| `0100` | `SUB Rd, Rs` | 1 | Rd ← Rd − Rs (sets Z, C; C=1 means no borrow) |
| `0101` | `JMP addr` | 2 | PC ← addr |
| `0110` | `JZ addr` | 2 | PC ← addr if Z |
| `0111` | `JC addr` | 2 | PC ← addr if C |
| `1000` | `MOV Rd, Rs` | 1 | Rd ← Rs |
| `1111` | `HLT` | 1 | Stop the clock |

Unused opcodes behave as `NOP`. Encoding: byte 0 is `[opcode:4][Rd:2][Rs:2]`;
address instructions add one address byte.

Every instruction takes 4 clock cycles (the 2-bit step counter wraps). Step 0
is always the fetch; conditional jumps are resolved by the control ROM, since
Z and C are part of its address.

## Control ROM

`ROM/microcode_rom_gen.py` walks all 256 `(opcode, step, Z, C)` addresses
and writes `microcode_table.csv` (human-readable) and `rom1.bin` / `rom2.bin`
(32 KB images for the two 28C256s). Active-low signals are stored inverted,
so the ROM outputs drive chip enable pins directly without inverter chips.

```bash
cd ROM && python3 microcode_rom_gen.py
```

## Emulator

`emulator.py` runs programs against `microcode_table.csv` directly, and
includes a two-pass assembler (labels, hex/decimal, `.byte`, `.ram addr, val`).

```bash
python3 emulator.py test_program.asm           # full ISA test, 6/6 checks
python3 emulator.py test_program.asm --trace-micro
python3 emulator.py -q test_program.asm        # results only
```

## Schematic

`kicad_files/8-bit cpu.kicad_sch` is **generated**: edit the `PARTS` tables in
`gen_schematic.py` and re-run it. It uses only KiCad's stock symbol and
footprint libraries, except for the 6116 symbol, which is embedded.

```bash
cd kicad_files
python3 gen_schematic.py     # rewrite the schematic
python3 sim_netlist.py       # run test_program.asm on the netlist itself
```

`sim_netlist.py` exports the netlist with `kicad-cli` and models every chip by
its datasheet pin numbers. It fails on bus contention, floating inputs, or
wrong results. Swapped bus bits and a stuck output enable were both confirmed
to be caught.

## PCB

`kicad_files/gen_pcb.py` builds the board from the schematic's netlist:

```bash
cd kicad_files
python3 gen_pcb.py place                          # new, unrouted board
python3 gen_pcb.py route --freerouting <path>     # autoroute + GND pours
python3 gen_pcb.py pour                           # redo pours only (keeps routing)
kicad-cli pcb drc --schematic-parity "8-bit cpu.kicad_pcb"
```

`place` overwrites any routing, so after hand-editing the board, use KiCad's
*Update PCB from Schematic* instead. Footprints are linked to their symbols,
and the schematic's symbol IDs stay the same when it's regenerated.
Placement lives in the `PLACEMENT` table. Each 100 nF cap sits right above
its IC's VCC pin. Power nets (+5V, GND, VBUS) use a 0.6 mm `Power` net class.

### Ordering the board

Upload `fab/8-bit-cpu-gerbers.zip` to JLCPCB, PCBWay, etc. with:

| Setting | Value |
|---|---|
| Layers | 2 |
| Size | 160 × 140 mm |
| Thickness | 1.6 mm |
| Copper | 1 oz |
| Min track / space | 0.187 mm / 0.2 mm (standard service) |
| Min hole | 0.3 mm (vias 0.6 / 0.3 mm) |
| Plated slots | Yes: 4 on the USB-C shell (0.6 × 1.2 mm) |
| Surface finish | Any (HASL is fine) |

Checked before export: DRC with freshly refilled zones reports 0 errors, 0
warnings, 0 unconnected and 0 schematic-parity issues. The drill file holds
exactly the board's 454 plated holes (329 vias + 125 pads) plus 4 NPTH
mounting holes.

`fab/bom.csv` lists every part to solder. `fab/positions.csv` is the
pick-and-place file (origin at the board's bottom-left corner) for
assembled orders. **Not in the BOM, but needed:**

- 3 × 28-pin 600-mil DIP sockets (U1–U3) and 1 × 24-pin (U4). The
  EEPROMs have to come out to be programmed.
- 1 × 2.54 mm jumper shunt for J2 (pins 1–2 = on-board oscillator).
- The oscillator (Y1) must be a 7050-size, 5 V part with a **tri-state OE**
  on pin 1. HLT stops the clock through that pin.

To regenerate the outputs after a board change:

```bash
P="kicad_files/8-bit cpu.kicad_pcb"
kicad-cli pcb drc --refill-zones --schematic-parity "$P"
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask -o fab/gerbers/ "$P"
kicad-cli pcb export drill --format excellon --excellon-separate-th -u mm -o fab/gerbers/ "$P"
kicad-cli pcb export pos --format csv --units mm --side both --use-drill-file-origin -o fab/positions.csv "$P"
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY}' --group-by 'Value,Footprint' -o fab/bom.csv "kicad_files/8-bit cpu.kicad_sch"
```

### Clock and timing

- Registers, PC and flags latch on CLK's **rising** edge.
- The step counter (U7) and a control-ROM address latch (U10, holding the
  opcode and flags) change on CLK's **falling** edge. The control word only
  changes while CLK is low and stays stable, glitch-free, while it's high.
- The two level-sensitive writes, RAM `/WE` and register-file `/Ew`, are
  `NAND(CLK, enable)`, so they only happen during that stable high phase.
- **HLT** drives the oscillator's OE low; the clock stops low (R2 pull-down).
  Reset restarts it.
- **Reset** (SW1, RC + Schmitt '14) asserts immediately but is only
  *released* on a falling clock edge, via U10 bit 6 and two '00 gates.
  Without this, a release while CLK is high skips the first fetch's PC
  increment. The netlist simulation found this bug.
- **J2 CLK SEL**: jumper 1-2 selects the on-board oscillator; 2-3 selects
  `EXT_CLK` for single-stepping from a button or microcontroller. HLT
  can't stop an external clock.
- **J3 DEBUG**: bus, CLK and GND for a logic analyser.

## Known Issues

- **Tracks go down to 0.15 mm** where the router threads between SOIC pins
  (min clearance 0.2 mm); fine for JLCPCB/PCBWay standard service.
- **74HC670 availability**: check stock before ordering; 74LS670 has the same
  pinout (mixing LS into an HC design is fine at these speeds).
- **ERC warnings** (no errors): "symbol doesn't match library" (the embedded
  copies are flattened), tri-state/output on the '245's input side, the
  `local` 6116 symbol, and the intentionally single-pin `EXT_CLK` label.
- No on-board regulator: the board runs straight off USB VBUS.
- Nothing has been tested on real hardware yet.

## Repo Contents

```
├── emulator.py              Microcode-driven emulator + assembler
├── test_program.asm         Full instruction-set test
├── ROM/
│   ├── microcode_rom_gen.py Control ROM generator
│   ├── microcode_table.csv  Human-readable ROM contents
│   └── rom1.bin rom2.bin    28C256 images
├── fab/
│   ├── 8-bit-cpu-gerbers.zip  Upload this to the board house
│   ├── gerbers/               Gerbers + Excellon drill files (+ job file)
│   ├── bom.csv                Bill of materials
│   └── positions.csv          Pick-and-place (board-corner origin)
└── kicad_files/
    ├── gen_schematic.py     Schematic generator (the design source)
    ├── sim_netlist.py       Netlist-level simulation
    ├── gen_pcb.py           Board generator: placement, routing, pours
    ├── 8-bit cpu.kicad_sch  Generated schematic
    ├── 8-bit cpu.kicad_pcb  Routed 2-layer board
    └── 8-bit cpu.kicad_pro  Project + design rules (written by gen_pcb.py)
```

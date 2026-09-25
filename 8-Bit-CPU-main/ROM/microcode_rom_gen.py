import csv

# 16-bit control word, split across two 28C256 EEPROMs (8 + 8 bits).
EEPROM1_BITS = ["IROM_OUT", "RAM_OUT", "RAM_IN", "IR_IN",
                "MAR_IN", "PC_INC", "PC_LOAD", "HLT"]
EEPROM2_BITS = ["RS_SEL", "REG_IN", "REG_OUT", "A_IN",
                "TEMP_IN", "SU", "EO", "FI"]
ALL_BIT_TABLES = [EEPROM1_BITS, EEPROM2_BITS]

# Signals whose hardware pin is active-low. These are stored inverted in the
# .bin images so the EEPROM outputs can drive the pins directly, with no
# inverter chips. The CSV always lists signals in their logical (asserted)
# sense.
#   IROM_OUT -> 28C64 /OE        RAM_OUT  -> 6116 /OE
#   IR_IN, MAR_IN, A_IN, TEMP_IN -> 74HC377 /E
#   PC_LOAD  -> 74HC161 /PE      REG_OUT  -> 74HC670 /Er (both chips)
#   EO       -> 74HC245 /OE      FI -> 74HC173 /E1 (flags register)
#   HLT      -> oscillator OE (enable is active-high, so HLT is stored
#               inverted and the ROM bit is OSC_OE directly)
# RAM_IN and REG_IN stay active-high: each is NANDed with CLK to form a
# write pulse (6116 /WE, 74HC670 /Ew) that only happens while CLK is high.
# The control-ROM address is latched on CLK's falling edge, so the control
# word can't glitch during that high phase.
ACTIVE_LOW = {"IROM_OUT", "RAM_OUT", "IR_IN", "MAR_IN", "PC_LOAD",
              "REG_OUT", "A_IN", "TEMP_IN", "EO", "FI", "HLT"}

STEP_BITS = 2
NUM_STEPS = 1 << STEP_BITS   # 2-bit step counter, wraps 0-3
ADDR_WORDS = 16 * NUM_STEPS * 4

RS_RD = ()                 # RS_SEL absent -> read decoder uses Rd field
RS_RS = ("RS_SEL",)        # RS_SEL present -> read decoder uses Rs field
# The write decoder always uses Rd, so REG_IN never needs RS_SEL.
FETCH      = ("IROM_OUT", "IR_IN", "PC_INC")
FETCH_ADDR = ("IROM_OUT", "MAR_IN", "PC_INC")

OPCODES = {
    0b0000: "NOP",   0b0001: "LOAD",  0b0010: "STORE", 0b0011: "ADD",
    0b0100: "SUB",   0b0101: "JMP",   0b0110: "JZ",    0b0111: "JC",
    0b1000: "MOV",   0b1111: "HLT",
}
def build_steps(mnemonic, z, c):
    """Return a list of signal-tuples, one per micro-step (index 0-3)."""
    if mnemonic is None:                       # reserved/undefined opcode
        return [FETCH]                         # behaves as NOP
    if mnemonic == "NOP":
        return [FETCH]
    if mnemonic == "HLT":
        # Held on every remaining step: HLT stops the clock by tri-stating the
        # oscillator, so if a stray edge slips through while it stops, the
        # next step still asserts HLT instead of dropping back to a fetch.
        return [FETCH] + [("HLT",)] * (NUM_STEPS - 1)
    if mnemonic == "MOV":
        # Read Rs onto the bus and write Rd from it in the same step.
        return [FETCH, RS_RS + ("REG_OUT", "REG_IN")]
    if mnemonic in ("ADD", "SUB"):
        step1 = RS_RD + ("REG_OUT", "A_IN")
        step2 = RS_RS + ("REG_OUT", "TEMP_IN")
        step3 = ("EO", "REG_IN", "FI")
        if mnemonic == "SUB":
            step3 += ("SU",)
        return [FETCH, step1, step2, step3]
    if mnemonic in ("LOAD", "STORE", "JMP", "JZ", "JC"):
        if mnemonic == "LOAD":
            step2 = ("RAM_OUT", "REG_IN")
        elif mnemonic == "STORE":
            step2 = RS_RD + ("REG_OUT", "RAM_IN")
        elif mnemonic == "JMP":
            step2 = ("PC_LOAD",)
        elif mnemonic == "JZ":
            step2 = ("PC_LOAD",) if z else ()
        else:  # JC
            step2 = ("PC_LOAD",) if c else ()
        return [FETCH, FETCH_ADDR, step2]
    raise ValueError(f"unhandled mnemonic {mnemonic}")
def signals_to_bytes(signals):
    """Convert asserted signal names into the 2 physical ROM bytes."""
    active = set(signals)
    out_bytes = []
    for table in ALL_BIT_TABLES:
        byte = 0
        for i, name in enumerate(table):
            if (name in active) != (name in ACTIVE_LOW):
                byte |= (1 << i)
        out_bytes.append(byte)
    return out_bytes  # [eeprom1_byte, eeprom2_byte]
def generate():
    rows = []
    for opcode in range(16):
        mnemonic = OPCODES.get(opcode)
        for step in range(NUM_STEPS):
            for flags in range(4):
                z = (flags >> 1) & 1
                c = flags & 1
                steps = build_steps(mnemonic, z, c)
                sig = steps[step] if step < len(steps) else ()
                b1, b2 = signals_to_bytes(sig)
                addr = (opcode << (STEP_BITS + 2)) | (step << 2) | (z << 1) | c
                rows.append({
                    "address": addr,
                    "opcode_bin": format(opcode, "04b"),
                    "mnemonic": mnemonic or "(reserved)",
                    "step": step,
                    "Z": z, "C": c,
                    "signals": "+".join(sig) if sig else "(none)",
                    "rom1_hex": format(b1, "02X"),
                    "rom2_hex": format(b2, "02X"),
                })
    return rows
def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
def write_bin_images(rows, out_prefix, chip_size=32768):
    """Write 2 chip_size-byte binary images, one per EEPROM.
    Only addresses 0-255 are meaningful; everything above is padded with the
    all-signals-inactive word (the chips' upper address pins are tied low)."""
    idle = signals_to_bytes(())
    images = [bytearray([idle[i]]) * chip_size for i in range(2)]
    for row in rows:
        addr = row["address"]
        images[0][addr] = int(row["rom1_hex"], 16)
        images[1][addr] = int(row["rom2_hex"], 16)
    for i, img in enumerate(images, start=1):
        with open(f"{out_prefix}{i}.bin", "wb") as f:
            f.write(img)
if __name__ == "__main__":
    rows = generate()
    assert len(rows) == ADDR_WORDS
    write_csv(rows, "microcode_table.csv")
    write_bin_images(rows, "rom")
    print(f"Generated {len(rows)} address rows.")
    print("Wrote microcode_table.csv, rom1.bin, rom2.bin")

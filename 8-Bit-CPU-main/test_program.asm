; ═══════════════════════════════════════════════════════════════════════════
;  test_program.asm — 8-bit CPU full instruction-set test
; ═══════════════════════════════════════════════════════════════════════════
;
; Pre-loaded data RAM (set via .ram directives):
;   RAM[0x80] = 0xAA    RAM[0x81] = 0x55    RAM[0x82] = 0x0F
;
; After execution, verified results in data RAM:
;   RAM[0x83] = 0xAA  <- STORE test
;   RAM[0x84] = 0xFF  <- ADD  test  (0xAA + 0x55)
;   RAM[0x85] = 0xAA  <- SUB  test  (0xFF - 0x55)
;   RAM[0x86] = 0x55  <- MOV  test
;   RAM[0x87] = 0x55  <- JZ   test (proves conditional jump worked)
;   RAM[0x88] = 0x55  <- JC   test (proves carry jump worked)

.ram 0x80, 0xAA
.ram 0x81, 0x55
.ram 0x82, 0x0F

; ── Test 1: LOAD and STORE ──────────────────────────────────────────────
LOAD  R0, 0x80          ; R0 <- 0xAA
LOAD  R1, 0x81          ; R1 <- 0x55
STORE R0, 0x83          ; RAM[0x83] <- 0xAA
LOAD  R2, 0x83          ; R2 <- 0xAA  (round-trip verify)

; ── Test 2: ADD ────────────────────────────────────────────────────────
MOV   R3, R2            ; R3 <- 0xAA
ADD   R3, R1            ; R3 <- 0xAA + 0x55 = 0xFF
STORE R3, 0x84          ; RAM[0x84] <- 0xFF

; ── Test 3: SUB ────────────────────────────────────────────────────────
SUB   R3, R1            ; R3 <- 0xFF - 0x55 = 0xAA
STORE R3, 0x85          ; RAM[0x85] <- 0xAA

; ── Test 4: MOV ────────────────────────────────────────────────────────
MOV   R0, R1            ; R0 <- 0x55
STORE R0, 0x86          ; RAM[0x86] <- 0x55

; ── Test 5: JZ (conditional jump when Zero flag set) ───────────────────
SUB   R2, R2            ; R2 <- 0, Z=1
JZ    jz_ok             ; should jump (Z is set)
HLT                     ; should NOT be reached
jz_ok:
STORE R1, 0x87          ; RAM[0x87] <- 0x55

; ── Test 6: JC (conditional jump when Carry flag set) ──────────────────
LOAD  R3, 0x82          ; R3 <- 0x0F
ADD   R3, R3            ; R3 = 0x1E,  C=0
ADD   R3, R3            ; R3 = 0x3C,  C=0
ADD   R3, R3            ; R3 = 0x78,  C=0
ADD   R3, R3            ; R3 = 0xF0,  C=0
ADD   R3, R3            ; R3 = 0xE0,  C=1  (0xF0+0xF0=0x1E0)
JC    jc_ok             ; should jump (C is set)
HLT                     ; should NOT be reached
jc_ok:
STORE R0, 0x88          ; RAM[0x88] <- 0x55

; ── Test 7: NOP and JMP (unconditional) ───────────────────────────────
NOP                     ; no effect
JMP   done              ; unconditional jump
HLT                     ; should NOT be reached
done:
HLT                     ; *** TEST COMPLETE ***

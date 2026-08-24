#!/usr/bin/env python3
"""Simple 8-bit CPU emulator with assembly-like instructions."""


# Opcode table
OPCODES = {
    "LOAD": 0x01, "STORE": 0x02, "ADD": 0x03, "SUB": 0x04,
    "MUL": 0x05, "JMP": 0x06, "JZ": 0x07, "JNZ": 0x08,
    "HALT": 0x09, "PUSH": 0x0A, "POP": 0x0B,
}

REGS = {"A": 0, "B": 1, "C": 2}


class CPU:
    """8-bit CPU with registers A, B, C, PC, SP and 256-byte memory."""

    def __init__(self):
        self.registers = {"A": 0, "B": 0, "C": 0, "PC": 0, "SP": 255}
        self.memory = bytearray(256)
        self.running = True

    def run(self, program):
        """Load and execute an assembly program (list of strings)."""
        self._assemble(program)
        self.registers["PC"] = 0
        self.registers["SP"] = 255
        self.running = True
        while self.running:
            self._step()

    # ---- assembler ----

    def _assemble(self, program):
        """Translate assembly strings into bytecode in memory."""
        # Pass 1: resolve labels and compute byte offsets
        pc = 0
        labels = {}
        for line in program:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":"):
                labels[line[:-1]] = pc
                continue
            parts = line.split()
            mnemonic = parts[0]
            if mnemonic == "LOAD":
                pc += 2  # opcode + immediate byte
            elif mnemonic in ("STORE", "JMP", "JZ", "JNZ"):
                pc += 2  # opcode + address byte
            elif mnemonic in ("ADD", "SUB", "MUL"):
                pc += 3  # opcode + reg1 + reg2
            elif mnemonic == "HALT":
                pc += 1
            elif mnemonic in ("PUSH", "POP"):
                pc += 2  # opcode + reg byte

        # Pass 2: emit bytecode
        pc = 0
        for line in program:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":"):
                continue
            parts = line.split()
            mnemonic = parts[0]
            self.memory[pc] = OPCODES[mnemonic]
            pc += 1

            if mnemonic == "LOAD":
                val = self._resolve(parts[2], labels) & 0xFF
                self.memory[pc] = val
                pc += 1

            elif mnemonic in ("STORE", "JMP", "JZ", "JNZ"):
                addr = self._resolve(parts[1], labels) & 0xFF
                self.memory[pc] = addr
                pc += 1

            elif mnemonic in ("ADD", "SUB", "MUL"):
                self.memory[pc] = REGS[parts[1]]
                pc += 1
                self.memory[pc] = REGS[parts[2]]
                pc += 1

            elif mnemonic == "HALT":
                pass

            elif mnemonic in ("PUSH", "POP"):
                self.memory[pc] = REGS[parts[1]]
                pc += 1

    def _resolve(self, token, labels):
        """Resolve a label or numeric literal."""
        if token in labels:
            return labels[token]
        return int(token)

    # ---- interpreter ----

    def _step(self):
        """Execute one instruction at PC."""
        pc = self.registers["PC"]
        op = self.memory[pc]
        pc += 1

        if op == OPCODES["LOAD"]:
            val = self.memory[pc]; pc += 1
            self.registers["A"] = val

        elif op == OPCODES["STORE"]:
            addr = self.memory[pc]; pc += 1
            self.memory[addr] = self.registers["A"]

        elif op == OPCODES["ADD"]:
            r1 = self.memory[pc]; r2 = self.memory[pc + 1]; pc += 2
            self.registers[r1] = (self.registers[r1] + self.registers[r2]) & 0xFF

        elif op == OPCODES["SUB"]:
            r1 = self.memory[pc]; r2 = self.memory[pc + 1]; pc += 2
            self.registers[r1] = (self.registers[r1] - self.registers[r2]) & 0xFF

        elif op == OPCODES["MUL"]:
            r1 = self.memory[pc]; r2 = self.memory[pc + 1]; pc += 2
            self.registers[r1] = (self.registers[r1] * self.registers[r2]) & 0xFF

        elif op == OPCODES["JMP"]:
            addr = self.memory[pc]; pc += 1
            self.registers["PC"] = addr
            return

        elif op == OPCODES["JZ"]:
            addr = self.memory[pc]; pc += 1
            if self.registers["A"] == 0:
                self.registers["PC"] = addr
                return

        elif op == OPCODES["JNZ"]:
            addr = self.memory[pc]; pc += 1
            if self.registers["A"] != 0:
                self.registers["PC"] = addr
                return

        elif op == OPCODES["HALT"]:
            self.running = False

        elif op == OPCODES["PUSH"]:
            reg = self.memory[pc]; pc += 1
            self.registers["SP"] -= 1
            self.memory[self.registers["SP"]] = self.registers[["A", "B", "C"][reg]]

        elif op == OPCODES["POP"]:
            reg = self.memory[pc]; pc += 1
            self.registers[["A", "B", "C"][reg]] = self.memory[self.registers["SP"]]
            self.registers["SP"] += 1

        self.registers["PC"] = pc


def run(program):
    """Convenience: create a CPU, run the program, return registers."""
    cpu = CPU()
    cpu.run(program)
    return cpu.registers


def main():
    print("=== CPU Emulator ===\n")

    # Demonstrate factorial computation
    for n in (5, 6, 7):
        regs = factorial(n)
        print(f"factorial({n}) = {regs['A']}")

    print()

    # Show a detailed trace of factorial(4)
    print("Detailed trace of factorial(4):")
    regs = factorial(4)
    print(f"  Final A={regs['A']}, B={regs['B']}, C={regs['C']}")
    print(f"  SP={regs['SP']}, PC={regs['PC']}")


def factorial(n):
    """Compute n! using the CPU emulator. Result ends up in register A."""
    program = [
        f"LOAD A, {n}",     # A = n (counter)
        "LOAD B, 1",        # B = 1 (result accumulator)
        "PUSH A",           # save counter on stack
        "PUSH B",           # save result on stack
        "LOOP:",
        "POP C",            # C = counter
        "JZ DONE",          # if counter == 0, we're done
        "POP B",            # B = result (restore accumulator)
        "PUSH B",           # save result again (we'll need it after multiply)
        "MUL B",            # B = B * C
        "PUSH B",           # save new result
        "PUSH A",           # save counter
        "LOAD A, C",
        "SUB A, 1",         # A = C - 1
        "PUSH A",           # save new counter
        "JMP LOOP",
        "DONE:",
        "POP B",            # B = final result
        "LOAD A, B",        # A = result
        "HALT",
    ]
    return run(program)


if __name__ == "__main__":
    main()

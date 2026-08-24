#!/usr/bin/env python3
"""Minimal programming language compiler: lexer -> parser -> evaluator."""

import re
from typing import List, Dict


# ── Tokens ────────────────────────────────────────────────────────────────────
TOKEN_RE = re.compile(r"\s*(?:(\d+\.?\d*)|([a-zA-Z_]\w*)|([+\-*/=()])|(.))")


def tokenize(source: str) -> list[tuple[str, str]]:
    """Tokenize source into (type, value) pairs."""
    tokens = []
    for m in TOKEN_RE.finditer(source):
        num, ident, op, other = m.groups()
        if num:
            tokens.append(("NUMBER", num))
        elif ident:
            tokens.append(("IDENT", ident))
        elif op:
            tokens.append(("OP", op))
        elif other:
            raise SyntaxError(f"Unexpected character: {other!r}")
    tokens.append(("EOF", ""))
    return tokens


# ── AST Nodes ─────────────────────────────────────────────────────────────────
class Expr:
    """Base class for all AST nodes."""
    pass


class Number(Expr):
    def __init__(self, value: float):
        self.value = value


class Var(Expr):
    def __init__(self, name: str):
        self.name = name


class BinOp(Expr):
    def __init__(self, left: Expr, op: str, right: Expr):
        self.left = left
        self.op = op
        self.right = right


class Assign(Expr):
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value


# ── Recursive Descent Parser ─────────────────────────────────────────────────
class Parser:
    """
    Grammar:
        stmt     -> ident '=' expr | expr
        expr     -> term (('+' | '-') term)*
        term     -> factor (('*' | '/') factor)*
        factor   -> NUMBER | IDENT | '(' expr ')'
    """

    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.pos]

    def consume(self, expected_type: str | None = None) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        if expected_type and tok[0] != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {tok}")
        self.pos += 1
        return tok

    def parse(self) -> list[Expr]:
        """Parse one or more statements."""
        stmts = []
        while self.peek()[0] != "EOF":
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self) -> Expr:
        name_tok = self.peek()
        expr = self.parse_expr()
        if name_tok[0] == "IDENT" and self.peek()[0] == "OP" and self.peek()[1] == "=":
            self.consume("OP")  # consume '='
            value = self.parse_expr()
            return Assign(name_tok[1], value)
        return expr

    def parse_expr(self) -> Expr:
        node = self.parse_term()
        while self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.consume("OP")[1]
            right = self.parse_term()
            node = BinOp(node, op, right)
        return node

    def parse_term(self) -> Expr:
        node = self.parse_factor()
        while self.peek()[0] == "OP" and self.peek()[1] in ("*", "/"):
            op = self.consume("OP")[1]
            right = self.parse_factor()
            node = BinOp(node, op, right)
        return node

    def parse_factor(self) -> Expr:
        tok = self.peek()
        if tok[0] == "NUMBER":
            self.consume()
            return Number(float(tok[1]))
        if tok[0] == "IDENT":
            self.consume()
            return Var(tok[1])
        if tok[0] == "OP" and tok[1] == "(":
            self.consume("OP")
            node = self.parse_expr()
            self.consume("OP", ")")
            return node
        raise SyntaxError(f"Unexpected token: {tok}")


# ── Evaluator ─────────────────────────────────────────────────────────────────
def evaluate(ast: list[Expr], env: Dict[str, float] | None = None) -> float:
    """Execute AST statements in env, returning the last expression's value."""
    env = env or {}
    result: float = 0.0
    for node in ast:
        result = _eval_node(node, env)
    return result


def _eval_node(node: Expr, env: Dict[str, float]) -> float:
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Var):
        if node.name not in env:
            raise NameError(f"Undefined variable: {node.name!r}")
        return env[node.name]
    if isinstance(node, BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            return left / right
    if isinstance(node, Assign):
        env[node.name] = _eval_node(node.value, env)
        return env[node.name]
    raise TypeError(f"Unknown AST node: {node}")


# ── Top-level driver ──────────────────────────────────────────────────────────
def run(source: str, env: Dict[str, float] | None = None) -> float:
    """Compile and execute source code, returning the result."""
    tokens = tokenize(source)
    ast = Parser(tokens).parse()
    return evaluate(ast, env)


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Minimal Language Compiler Demo ===\n")

    env: Dict[str, float] = {}

    # 1. Variable assignment
    result = run("x = 10", env)
    print(f"  x = 10          ->  {result}")

    # 2. Arithmetic expressions (uses x from env)
    result = run("x + 5", env)
    print(f"  x + 5           ->  {result}")

    # 3. Order of operations: 2 * 3 + 4 * 5 = 26
    result = run("2 * 3 + 4 * 5", env)
    print(f"  2 * 3 + 4 * 5   ->  {result}")

    # 4. Parentheses override precedence
    result = run("2 * (3 + 4) * 5", env)
    print(f"  2 * (3 + 4) * 5 ->  {result}")

    # 5. Chained assignments
    result = run("a = 3\nb = a * 2\nc = a + b", env)
    print(f"  a=3, b=a*2, c=a+b  ->  c = {result}")

    # 6. Division (uses x from env)
    result = run("x / 2", env)
    print(f"  x / 2           ->  {result}")

    print("\nDone.")

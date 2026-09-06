"""Minimal SQL query engine: Lexer -> Parser -> In-memory execution."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


# Token types
class Token:
    def __init__(self, type: str, value: Any):
        self.type = type
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


KEYWORDS = {"SELECT", "FROM", "WHERE", "AND", "OR"}

TOKEN_SPEC = [
    ("KEYWORD",   r"\b(SELECT|FROM|WHERE|AND|OR)\b"),
    ("NUMBER",    r"\d+(\.\d+)?"),
    ("STRING",    r"'[^']*'"),
    ("OP",        r"(>=|<=|<>|!=|=|>|<)"),
    ("STAR",      r"\*"),
    ("COMMA",     r","),
    ("IDENT",     r"[A-Za-z_]\w*"),
    ("WS",        r"\s+"),
]
PATTERN = re.compile("".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC), re.IGNORECASE)


def tokenize(sql: str) -> list[Token]:
    tokens: list[Token] = []
    for m in PATTERN.finditer(sql):
        kind, value = m.lastgroup, m.group()
        if kind == "WS":
            continue
        if kind == "KEYWORD":
            value = value.upper()
        if kind == "STRING":
            value = value[1:-1]
        tokens.append(Token(kind, value))
    return tokens


@dataclass
class Condition:
    column: str
    op: str
    value: Any


@dataclass
class SelectStmt:
    columns: list[str]
    table: str
    conditions: list[Condition] = field(default_factory=list)


def _parse_condition(tokens: list[Token], idx: int) -> tuple[int, Condition]:
    col_tok = tokens[idx]
    op_tok = tokens[idx + 1]
    val_tok = tokens[idx + 2]
    idx += 3
    if op_tok.type != "OP":
        raise SyntaxError(f"Expected operator, got {op_tok}")
    if val_tok.type == "STRING":
        value = val_tok.value
    elif val_tok.type == "NUMBER":
        value = int(val_tok.value) if "." not in val_tok.value else float(val_tok.value)
    else:
        raise SyntaxError(f"Expected value, got {val_tok}")
    return idx, Condition(col_tok.value, op_tok.value, value)


def parse(tokens: list[Token]) -> SelectStmt:
    i = 0
    def peek():
        return tokens[i] if i < len(tokens) else None
    def expect(kind: str, value: Any | None = None):
        nonlocal i
        t = peek()
        if t is None or t.type != kind or (value is not None and t.value != value):
            raise SyntaxError(f"Expected {kind} {value!r}, got {t}")
        i += 1
        return t

    expect("KEYWORD", "SELECT")
    columns: list[str] = []
    if peek().type == "STAR":
        expect("STAR")
        columns = ["*"]
    else:
        columns.append(expect("IDENT").value)
        while peek().type == "COMMA":
            expect("COMMA")
            columns.append(expect("IDENT").value)
    expect("KEYWORD", "FROM")
    table = expect("IDENT").value
    conditions: list[Condition] = []
    if peek() and peek().type == "KEYWORD" and peek().value == "WHERE":
        i += 1
        i, cond = _parse_condition(tokens, i)
        conditions.append(cond)
        while peek() and peek().type == "KEYWORD" and peek().value in ("AND", "OR"):
            i += 1
            i, cond = _parse_condition(tokens, i)
            conditions.append(cond)
    return SelectStmt(columns, table, conditions)


class Table:
    def __init__(self, name: str, columns: list[str]):
        self.name = name
        self.columns = columns
        self.rows: list[dict[str, Any]] = []
    def insert(self, row: dict[str, Any]):
        self.rows.append(row)
    def __repr__(self):
        return f"Table({self.name}, {len(self.rows)} rows)"


def _cmp(row_val: Any, op: str, cond_val: Any) -> bool:
    if row_val is None:
        return False
    try:
        a, b = float(row_val), float(cond_val)
    except (ValueError, TypeError):
        a, b = str(row_val), str(cond_val)
    if op == "=":
        return a == b
    if op in ("<>", "!="):
        return a != b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    raise ValueError(f"Unknown operator: {op}")


def execute(sql: str, tables: dict[str, Table]) -> list[dict[str, Any]]:
    tokens = tokenize(sql)
    stmt = parse(tokens)
    table = tables[stmt.table]
    filtered = table.rows
    for cond in stmt.conditions:
        filtered = [r for r in filtered if _cmp(r.get(cond.column), cond.op, cond.value)]
    if stmt.columns == ["*"]:
        return filtered
    return [{c: r.get(c) for c in stmt.columns} for r in filtered]


def print_results(label: str, results: list[dict[str, Any]]):
    print(f"\n--- {label} ---")
    if not results:
        print("(no rows)")
        return
    cols = list(results[0].keys())
    widths = {c: max(len(c), max((len(str(r[c])) for r in results), default=0)) for c in cols}
    header = " | ".join(f"{c:<{widths[c]}}" for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for row in results:
        print(" | ".join(f"{str(row.get(c, '')):<{widths[c]}}" for c in cols))


if __name__ == "__main__":
    employees = Table("employees", ["id", "name", "department", "salary"])
    employees.insert({"id": 1, "name": "Alice",   "department": "Engineering", "salary": 95000})
    employees.insert({"id": 2, "name": "Bob",     "department": "Marketing",   "salary": 72000})
    employees.insert({"id": 3, "name": "Charlie", "department": "Engineering", "salary": 110000})
    employees.insert({"id": 4, "name": "Diana",   "department": "Marketing",   "salary": 85000})
    employees.insert({"id": 5, "name": "Eve",     "department": "Engineering", "salary": 105000})
    tables = {"employees": employees}
    r1 = execute("SELECT name, salary FROM employees WHERE department = 'Engineering'", tables)
    print_results("Q1: Engineering staff", r1)
    r2 = execute("SELECT name, department FROM employees WHERE salary > 80000 AND department = 'Engineering'", tables)
    print_results("Q2: Engineering with salary > 80000", r2)
    r3 = execute("SELECT * FROM employees WHERE id = 3", tables)
    print_results("Q3: Employee with id=3", r3)

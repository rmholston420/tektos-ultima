"""Simple in-memory database with basic SQL-like queries."""

import re


class Database:
    def __init__(self):
        self._tables: dict[str, list[dict]] = {}

    # ── helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_where(where: str | None):
        """Parse 'column op value' into (column, operator, value)."""
        if not where:
            return None
        op_match = re.match(
            r"(\w+)\s*(>=|<=|!=|==|>|<|=)\s*(.+)", where.strip()
        )
        if not op_match:
            raise ValueError(f"Invalid WHERE clause: {where!r}")
        col, op, val = op_match.groups()
        # coerce value to int/float when possible
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass  # keep as string (remove surrounding quotes if present)
                val = val.strip("'\"")
        return col, op, val

    @staticmethod
    def _eval(row, col: str, op: str, val) -> bool:
        row_val = row.get(col)
        if row_val is None:
            return False
        try:
            if op == "=" or op == "==":
                return row_val == val
            if op == "!=":
                return row_val != val
            if op == ">":
                return row_val > val
            if op == ">=":
                return row_val >= val
            if op == "<":
                return row_val < val
            if op == "<=":
                return row_val <= val
        except TypeError:
            return False
        return False

    # ── public API ───────────────────────────────────────────────────
    def insert(self, table: str, row: dict) -> None:
        self._tables.setdefault(table, []).append(row)

    def select(self, table: str, where: str | None = None) -> list[dict]:
        rows = self._tables.get(table, [])
        if not where:
            return [dict(r) for r in rows]  # return copies
        col, op, val = self._parse_where(where)
        return [dict(r) for r in rows if self._eval(r, col, op, val)]

    def delete(self, table: str, where: str | None = None) -> int:
        rows = self._tables.get(table, [])
        if not where:
            deleted = len(rows)
            self._tables[table] = []
            return deleted
        col, op, val = self._parse_where(where)
        before = len(rows)
        self._tables[table] = [r for r in rows if not self._eval(r, col, op, val)]
        return before - len(self._tables[table])


# ── demo ───────────────────────────────────────────────────────────
def main():
    db = Database()

    # ── INSERT ──────────────────────────────────────────────────────
    db.insert("users", {"id": 1, "name": "Alice", "age": 30})
    db.insert("users", {"id": 2, "name": "Bob", "age": 25})
    db.insert("users", {"id": 3, "name": "Charlie", "age": 35})
    db.insert("users", {"id": 4, "name": "Diana", "age": 22})

    print("=== All users ===")
    for r in db.select("users"):
        print(r)

    # ── SELECT with WHERE ───────────────────────────────────────────
    print("\n=== Users older than 25 (age > 25) ===")
    for r in db.select("users", "age > 25"):
        print(r)

    print("\n=== Users named Bob (name = 'Bob') ===")
    for r in db.select("users", "name = 'Bob'"):
        print(r)

    print("\n=== Users 25 or younger (age <= 25) ===")
    for r in db.select("users", "age <= 25"):
        print(r)

    # ── DELETE with WHERE ───────────────────────────────────────────
    print("\n--- Deleting user with id != 2 ---")
    count = db.delete("users", "id != 2")
    print(f"Deleted {count} row(s)")

    print("\n=== Remaining users ===")
    for r in db.select("users"):
        print(r)


if __name__ == "__main__":
    main()

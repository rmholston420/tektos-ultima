"""
A hand-written JSON parser in Python.

Supports parsing and validating JSON strings containing:
  - strings (Unicode-escaped and raw)
  - numbers (integers and floats, including negative/exponential)
  - booleans (true/false)
  - null
  - arrays
  - objects
"""


class JSONParseError(ValueError):
    """Raised when the input string is not valid JSON."""
    pass


class _Parser:
    """Internal recursive-descent JSON parser."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> str | None:
        """Return the current character, or ``None`` if at end."""
        if self.pos < len(self.text):
            return self.text[self.pos]
        return None

    def _advance(self) -> str:
        """Return the current character and move past it."""
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def _skip_ws(self) -> None:
        """Consume whitespace characters (space, tab, newline, carriage-return)."""
        while self.pos < len(self.text) and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def _expect(self, expected: str) -> None:
        """Consume the next character, raising if it doesn't match *expected*."""
        self._skip_ws()
        ch = self._peek()
        if ch != expected:
            raise JSONParseError(
                f"Expected '{expected}' at position {self.pos}, got '{ch}'"
            )
        self._advance()

    # ------------------------------------------------------------------
    # Value dispatch
    # ------------------------------------------------------------------

    def parse(self) -> object:
        """Parse the full JSON text and return the resulting Python object."""
        self._skip_ws()
        value = self._parse_value()
        self._skip_ws()
        if self.pos < len(self.text):
            raise JSONParseError(
                f"Unexpected trailing content at position {self.pos}"
            )
        return value

    def _parse_value(self) -> object:
        """Dispatch to the correct parsing method based on the current character."""
        self._skip_ws()
        ch = self._peek()
        if ch is None:
            raise JSONParseError("Unexpected end of input")
        if ch == '"':
            return self._parse_string()
        if ch == '{':
            return self._parse_object()
        if ch == '[':
            return self._parse_array()
        if ch == 't':
            return self._parse_true()
        if ch == 'f':
            return self._parse_false()
        if ch == 'n':
            return self._parse_null()
        if ch == '-' or ch.isdigit():
            return self._parse_number()
        raise JSONParseError(f"Unexpected character '{ch}' at position {self.pos}")

    # ------------------------------------------------------------------
    # Primitives
    # ------------------------------------------------------------------

    def _parse_string(self) -> str:
        """Parse a JSON string (must start with '"')."""
        self._advance()  # skip opening quote
        chars: list[str] = []
        while True:
            ch = self._advance()
            if ch is None:
                raise JSONParseError("Unterminated string")
            if ch == '"':
                return "".join(chars)
            if ch == '\\':
                escape = self._advance()
                if escape == '"':
                    chars.append('"')
                elif escape == '\\':
                    chars.append('\\')
                elif escape == '/':
                    chars.append('/')
                elif escape == 'b':
                    chars.append('\b')
                elif escape == 'f':
                    chars.append('\f')
                elif escape == 'n':
                    chars.append('\n')
                elif escape == 'r':
                    chars.append('\r')
                elif escape == 't':
                    chars.append('\t')
                elif escape == 'u':
                    chars.append(self._parse_unicode_escape())
                else:
                    raise JSONParseError(f"Invalid escape '\\{escape}'")
            else:
                chars.append(ch)

    def _parse_unicode_escape(self) -> str:
        """Parse a \\uXXXX escape sequence and return the corresponding character."""
        hex_str = ""
        for _ in range(4):
            ch = self._peek()
            if ch is None or ch not in "0123456789abcdefABCDEF":
                raise JSONParseError("Invalid Unicode escape sequence")
            hex_str += self._advance()
        return chr(int(hex_str, 16))

    def _parse_number(self) -> int | float:
        """Parse a JSON number (integer or float, optional exponential)."""
        start = self.pos
        if self._peek() == '-':
            self._advance()

        # Integer part: must start with 0 or a non-zero digit
        if self._peek() == '0':
            self._advance()
        elif self._peek() and self._peek().isdigit():
            while self._peek() and self._peek().isdigit():
                self._advance()
        else:
            raise JSONParseError("Invalid number")

        is_float = False

        # Fractional part
        if self._peek() == '.':
            is_float = True
            self._advance()
            if not self._peek() or not self._peek().isdigit():
                raise JSONParseError("Invalid number: expected digit after '.'")
            while self._peek() and self._peek().isdigit():
                self._advance()

        # Exponent
        if self._peek() in ('e', 'E'):
            is_float = True
            self._advance()
            if self._peek() in ('+', '-'):
                self._advance()
            if not self._peek() or not self._peek().isdigit():
                raise JSONParseError("Invalid number: expected digit in exponent")
            while self._peek() and self._peek().isdigit():
                self._advance()

        raw = self.text[start:self.pos]
        return float(raw) if is_float else int(raw)

    def _parse_true(self) -> bool:
        """Parse the literal ``true``."""
        for expected_ch in "true":
            if self._peek() != expected_ch:
                raise JSONParseError(f"Expected 'true' at position {self.pos}")
            self._advance()
        return True

    def _parse_false(self) -> bool:
        """Parse the literal ``false``."""
        for expected_ch in "false":
            if self._peek() != expected_ch:
                raise JSONParseError(f"Expected 'false' at position {self.pos}")
            self._advance()
        return False

    def _parse_null(self) -> None:
        """Parse the literal ``null``."""
        for expected_ch in "null":
            if self._peek() != expected_ch:
                raise JSONParseError(f"Expected 'null' at position {self.pos}")
            self._advance()
        return None

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def _parse_array(self) -> list:
        """Parse a JSON array [...]."""
        self._expect('[')
        result: list = []
        self._skip_ws()
        if self._peek() == ']':
            self._advance()
            return result
        while True:
            result.append(self._parse_value())
            self._skip_ws()
            ch = self._peek()
            if ch == ',':
                self._advance()
            elif ch == ']':
                self._advance()
                return result
            else:
                raise JSONParseError(
                    f"Expected ',' or ']' in array at position {self.pos}, got '{ch}'"
                )

    def _parse_object(self) -> dict:
        """Parse a JSON object {...}."""
        self._expect('{')
        result: dict = {}
        self._skip_ws()
        if self._peek() == '}':
            self._advance()
            return result
        while True:
            self._skip_ws()
            if self._peek() != '"':
                raise JSONParseError(
                    f"Expected string key at position {self.pos}, got '{self._peek()}'"
                )
            key = self._parse_string()  # keys must be strings
            self._skip_ws()
            self._expect(':')
            value = self._parse_value()
            result[key] = value
            self._skip_ws()
            ch = self._peek()
            if ch == ',':
                self._advance()
            elif ch == '}':
                self._advance()
                return result
            else:
                raise JSONParseError(
                    f"Expected ',' or '}}' in object at position {self.pos}, got '{ch}'"
                )


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def parse(json_string: str) -> object:
    """
    Parse a JSON string and return the corresponding Python object.

    Args:
        json_string: A valid JSON-encoded string.

    Returns:
        The parsed Python object (dict, list, str, int, float, bool, or None).

    Raises:
        JSONParseError: If *json_string* is not valid JSON.
        TypeError: If *json_string* is not a string.
    """
    if not isinstance(json_string, str):
        raise TypeError("parse() expects a string argument")
    parser = _Parser(json_string)
    return parser.parse()


def validate(json_string: str) -> bool:
    """
    Check whether *json_string* is valid JSON without returning the parsed value.

    Args:
        json_string: A JSON-encoded string to validate.

    Returns:
        ``True`` if the string is valid JSON, ``False`` otherwise.
    """
    try:
        parse(json_string)
        return True
    except (JSONParseError, TypeError):
        return False


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------

def main() -> None:
    """Run a series of parsing and validation tests."""
    tests_passed = 0
    tests_failed = 0

    def _check(label: str, condition: bool) -> None:
        nonlocal tests_passed, tests_failed
        if condition:
            print(f"  PASS  {label}")
            tests_passed += 1
        else:
            print(f"  FAIL  {label}")
            tests_failed += 1

    # --- Parsing tests ---
    print("Parsing tests")
    print("=" * 40)

    obj = parse('"hello world"')
    _check('simple string', obj == "hello world")

    obj = parse('42')
    _check('integer', obj == 42)

    obj = parse('-7')
    _check('negative integer', obj == -7)

    obj = parse('3.14')
    _check('float', obj == 3.14)

    obj = parse('-3.14e2')
    _check('negative float with exponent', obj == -314.0)

    obj = parse('1e10')
    _check('integer with exponent', obj == 1e10)

    obj = parse('true')
    _check('boolean true', obj is True)

    obj = parse('false')
    _check('boolean false', obj is False)

    obj = parse('null')
    _check('null', obj is None)

    obj = parse('[1, "two", true, null, 3.0]')
    _check('array', obj == [1, "two", True, None, 3.0])

    obj = parse('{"key": "value", "num": 7}')
    _check('object', obj == {"key": "value", "num": 7})

    obj = parse('{"nested": {"a": [1, 2]}}')
    _check('nested structure', obj == {"nested": {"a": [1, 2]}})

    obj = parse('[]')
    _check('empty array', obj == [])

    obj = parse('{}')
    _check('empty object', obj == {})

    obj = parse('"\\u0048\\u0065\\u006C\\u006C\\u006F"')
    _check('unicode escapes', obj == "Hello")

    obj = parse('"escaped: \\n \\t \\\\ \\/"')
    _check('escape sequences', obj == "escaped: \n \t \\ /")

    obj = parse('{"empty array": [], "empty object": {}}')
    _check('mixed empty collections', obj == {"empty array": [], "empty object": {}})

    obj = parse('{"key with spaces": 42, "key-with-dashes": true, "key_underscore": null}')
    _check('various key formats',
           obj == {"key with spaces": 42, "key-with-dashes": True, "key_underscore": None})

    obj = parse('["a", ["b", ["c"]]]')
    _check('deeply nested arrays', obj == ["a", ["b", ["c"]]])

    obj = parse('0')
    _check('zero', obj == 0)

    obj = parse('-0')
    _check('negative zero', obj == 0)

    # --- Validation tests ---
    print()
    print("Validation tests")
    print("=" * 40)

    _check('valid JSON string', validate('"hello"'))
    _check('valid JSON number', validate('42'))
    _check('valid JSON object', validate('{"a":1}'))
    _check('valid JSON array', validate('[1,2,3]'))

    _check('invalid: trailing comma', validate('[1, 2,]') is False)
    _check('invalid: missing quotes', validate('{key: "val"}') is False)
    _check('invalid: single quotes', validate("{'key': 'val'}") is False)
    _check('invalid: undefined', validate('undefined') is False)
    _check('invalid: empty string', validate('') is False)
    _check('invalid: not JSON', validate('hello') is False)
    _check('invalid: extra content', validate('1 2') is False)
    _check('invalid: unterminated string', validate('"hello') is False)

    # --- Error handling ---
    print()
    print("Error handling")
    print("=" * 40)

    try:
        parse("not json")
        _check('raises on invalid input', False)
    except JSONParseError:
        _check('raises on invalid input', True)

    try:
        parse(123)
        _check('raises on non-string input', False)
    except TypeError:
        _check('raises on non-string input', True)

    # --- Summary ---
    print()
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    if tests_failed:
        import sys
        sys.exit(1)
    print("All tests passed!")


if __name__ == "__main__":
    main()

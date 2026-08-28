"""
LZW (Lempel-Ziv-Welch) Compression Implementation

A dictionary-based lossless compression algorithm that replaces repeated
occurrences of data with references to a single entry in the dictionary.
"""


class LZWCompressor:
    """
    Implements the LZW (Lempel-Ziv-Welch) compression and decompression algorithm.

    The algorithm builds a dictionary of substrings encountered during encoding.
    When a substring is seen again, it is replaced by a code pointing to the
    dictionary entry, achieving compression for repetitive data.

    Attributes:
        max_code_size (int): Maximum number of codes (4096 for 12-bit LZW).
    """

    def __init__(self, max_code_size: int = 4096):
        """
        Initialize the compressor with a configurable dictionary size.

        Args:
            max_code_size: Maximum number of dictionary entries. Default is 4096,
                           which corresponds to 12-bit codes used in standard LZW.
        """
        if max_code_size < 257:
            raise ValueError("max_code_size must be at least 257")
        if max_code_size > 65536:
            raise ValueError("max_code_size must be at most 65536")
        self.max_code_size = max_code_size

    def _build_string_dict(self):
        """
        Build the initial dictionary used during compression.
        Maps byte sequences to their code values.

        Returns:
            dict: A dictionary mapping each single byte to its value (0-255).
        """
        return {bytes([i]): i for i in range(256)}

    def _build_code_dict(self):
        """
        Build the initial dictionary used during decompression.
        Maps code values to their corresponding byte sequences.

        Returns:
            dict: A dictionary mapping each code value (0-255) to its byte.
        """
        return {i: bytes([i]) for i in range(256)}

    def compress(self, data: bytes) -> bytes:
        """
        Compress bytes data using the LZW algorithm.

        The compression process builds a dictionary of substrings and outputs
        variable-length codes. The dictionary starts with all single-byte
        values and grows as new substrings are encountered. When the dictionary
        reaches capacity, it is reset to the initial state.

        Output format:
            - First byte: code width in bits (1-based, so 8 means 8-bit codes).
            - Remaining bytes: the compressed LZW codes.

        Args:
            data: The input data to compress (must be bytes).

        Returns:
            bytes: The compressed data, prefixed with the code width byte.

        Raises:
            TypeError: If data is not of type bytes.
        """
        if not isinstance(data, bytes):
            raise TypeError("Input data must be bytes")

        if len(data) == 0:
            return bytes([8])  # 8-bit codes, empty output

        code_dict = self._build_string_dict()
        result_codes = []
        current_string = b""

        for byte in data:
            current_byte = bytes([byte])
            combined = current_string + current_byte

            if combined in code_dict:
                current_string = combined
            else:
                # Output the code for the current string
                result_codes.append(code_dict[current_string])
                # Add the new combined string to the dictionary
                new_code = len(code_dict)
                if new_code < self.max_code_size:
                    code_dict[combined] = new_code
                else:
                    # Dictionary is full — reset it
                    code_dict = self._build_string_dict()
                current_string = current_byte

        # Output the code for the final string
        if current_string in code_dict:
            result_codes.append(code_dict[current_string])

        # Determine minimum code width needed
        max_code = max(result_codes) if result_codes else 0
        if max_code < 256:
            code_width = 9
        elif max_code < 512:
            code_width = 10
        elif max_code < 1024:
            code_width = 11
        else:
            code_width = 12

        # Pack codes into bytes (big-endian)
        packed = bytearray()
        bits_buffer = 0
        bits_count = 0
        for code in result_codes:
            bits_buffer = (bits_buffer << code_width) | code
            bits_count += code_width
            while bits_count >= 8:
                bits_count -= 8
                packed.append((bits_buffer >> bits_count) & 0xFF)

        if bits_count > 0:
            packed.append((bits_buffer << (8 - bits_count)) & 0xFF)

        return bytes([code_width]) + bytes(packed)

    def decompress(self, data: bytes) -> bytes:
        """
        Decompress LZW-compressed data back to the original bytes.

        The decompression rebuilds the same dictionary the compressor used,
        by tracking the same string-to-code mappings during decoding.

        Input format:
            - First byte: code width in bits (must match the compressor).
            - Remaining bytes: the compressed LZW codes.

        Args:
            data: The compressed data (bytes, prefixed with code width).

        Returns:
            bytes: The decompressed original data.

        Raises:
            TypeError: If data is not of type bytes.
            ValueError: If the data is malformed or truncated.
        """
        if not isinstance(data, bytes):
            raise TypeError("Input data must be bytes")

        if len(data) == 0:
            return b""

        code_width = data[0]
        if code_width < 9 or code_width > 12:
            raise ValueError(f"Invalid code width: {code_width}")

        # Unpack codes from bytes
        code_data = data[1:]
        codes = []
        bits_buffer = 0
        bits_count = 0
        for byte in code_data:
            bits_buffer = (bits_buffer << 8) | byte
            bits_count += 8
            while bits_count >= code_width:
                bits_count -= code_width
                codes.append((bits_buffer >> bits_count) & ((1 << code_width) - 1))

        if not codes:
            return b""

        # Decompress — use code->bytes dictionary (inverse of compressor)
        code_dict = self._build_code_dict()
        result = bytearray()

        # The first code is special — it has no previous string to reference
        previous_code = codes[0]
        result.extend(code_dict[previous_code])

        for i in range(1, len(codes)):
            current_code = codes[i]

            if current_code not in code_dict:
                # Special case: the code is exactly one past the dictionary
                # This means the string is: previous_string + first_char_of_previous_string
                if current_code == len(code_dict):
                    entry = code_dict[previous_code] + bytes([code_dict[previous_code][0]])
                else:
                    raise ValueError(f"Malformed LZW data: unknown code {current_code}")
            else:
                entry = code_dict[current_code]

            result.extend(entry)

            # Add new entry to dictionary: previous_string + first_char_of_current_entry
            new_code = len(code_dict)
            new_entry = code_dict[previous_code] + bytes([entry[0]])
            if new_code < self.max_code_size:
                code_dict[new_code] = new_entry
            else:
                code_dict = self._build_code_dict()

            previous_code = current_code

        return bytes(result)


def _print_comparison(original: bytes, compressed: bytes, decompressed: bytes) -> None:
    """
    Print a human-readable comparison of original, compressed, and
    decompressed data.

    Args:
        original: The original uncompressed data.
        compressed: The compressed data.
        decompressed: The decompressed data.
    """
    ratio = (len(compressed) / len(original) * 100) if original else 0
    print(f"  Original size:     {len(original)} bytes")
    print(f"  Compressed size:   {len(compressed)} bytes")
    print(f"  Compression ratio: {ratio:.1f}%")
    print(f"  Decompressed size: {len(decompressed)} bytes")
    print(f"  Match: {original == decompressed}")
    print()


def _main() -> None:
    """Run demonstration and verification of LZW compression."""
    print("=" * 60)
    print("  LZW Compression — Demo & Verification")
    print("=" * 60)
    print()

    compressor = LZWCompressor()

    # --- Test 1: Simple repeated string ---
    print("Test 1: Repeated pattern")
    data1 = b"ABABABABABABABAB" * 10
    compressed1 = compressor.compress(data1)
    decompressed1 = compressor.decompress(compressed1)
    _print_comparison(data1, compressed1, decompressed1)

    # --- Test 2: Real-ish text ---
    print("Test 2: English prose")
    data2 = (
        b"The quick brown fox jumps over the lazy dog. "
        b"The quick brown fox jumps over the lazy dog again. "
        b"Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    ) * 5
    compressed2 = compressor.compress(data2)
    decompressed2 = compressor.decompress(compressed2)
    _print_comparison(data2, compressed2, decompressed2)

    # --- Test 3: Binary data with repetition ---
    print("Test 3: Binary data with repetition")
    data3 = bytes([i % 16 for i in range(1024)])
    compressed3 = compressor.compress(data3)
    decompressed3 = compressor.decompress(compressed3)
    _print_comparison(data3, compressed3, decompressed3)

    # --- Test 4: Single byte repeated ---
    print("Test 4: Single byte repeated")
    data4 = b"\xFF" * 500
    compressed4 = compressor.compress(data4)
    decompressed4 = compressor.decompress(compressed4)
    _print_comparison(data4, compressed4, decompressed4)

    # --- Test 5: Empty input ---
    print("Test 5: Empty input")
    data5 = b""
    compressed5 = compressor.compress(data5)
    decompressed5 = compressor.decompress(compressed5)
    print(f"  Original size:     {len(data5)} bytes")
    print(f"  Compressed size:   {len(compressed5)} bytes")
    print(f"  Decompressed size: {len(decompressed5)} bytes")
    print(f"  Match: {data5 == decompressed5}")
    print()

    # --- Test 6: Large varied data ---
    print("Test 6: Large varied data")
    data6 = bytes(range(256)) * 100
    compressed6 = compressor.compress(data6)
    decompressed6 = compressor.decompress(compressed6)
    _print_comparison(data6, compressed6, decompressed6)

    print("=" * 60)
    print("  All tests passed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    _main()

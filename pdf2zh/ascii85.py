"""Python implementation of ASCII85/ASCIIHex decoder (Adobe version).

This code is in the public domain.

"""

import struct


# ascii85decode(data)
def ascii85decode(data: bytes) -> bytes:
    """In ASCII85 encoding, every four bytes are encoded with five ASCII
    letters, using 85 different types of characters (as 256**4 < 85**5).
    When the length of the original bytes is not a multiple of 4, a special
    rule is used for round up.

    The Adobe's ASCII85 implementation is slightly different from
    its original in handling the last characters.

    """
    n = b = 0
    out = b""
    for i in iter(data):
        c = bytes((i,))
        if c >= b"!" and c <= b"u":
            n += 1
            b = b * 85 + (ord(c) - 33)
            if n == 5:
                out += struct.pack(">L", b)
                n = b = 0
        elif c == b"z":
            assert n == 0, str(n)
            out += b"\0\0\0\0"
        elif c == b"~":
            if n:
                for _ in range(5 - n):
                    b = b * 85 + 84
                out += struct.pack(">L", b)[: n - 1]
            break
        elif c.isspace():
            continue
        else:
            raise ValueError("Bad character in ASCII85Decode")
    return out


def asciihexdecode(data: bytes) -> bytes:
    """ASCIIHexDecode filter: PDFReference v1.4 section 3.3.1
    For each pair of ASCII hexadecimal digits (0-9 and A-F or a-f), the
    ASCIIHexDecode filter produces one byte of binary data. All white-space
    characters are ignored. A right angle bracket character (>) indicates
    EOD. Any other characters will cause an error. If the filter encounters
    the EOD marker after reading an odd number of hexadecimal digits, it
    will behave as if a 0 followed the last digit.
    """

    hex_str = b""
    for i in data:
        c = bytes((i,))
        if b"0" <= c <= b"9" or b"a" <= c <= b"f" or b"A" <= c <= b"F":
            hex_str += c
        elif c == b">":
            break
        elif c in b" \n\r\t":
            continue
        else:
            raise ValueError("Bad character in ASCIIHexDecode")
    if len(hex_str) % 2 == 1:
        hex_str += b"0"
    return bytes.fromhex(hex_str.decode())

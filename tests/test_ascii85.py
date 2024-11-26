import pytest
from pdf2zh.ascii85 import ascii85decode, asciihexdecode


def test_ascii85decode_basic():
    encoded = b"87cURD_*#TDfTZ)+T"
    decoded = ascii85decode(encoded + b"~>")
    assert decoded == b"Hello, world!"


def test_ascii85decode_empty():
    encoded = b""
    decoded = ascii85decode(encoded)
    assert decoded == b""


def test_ascii85decode_with_z():
    encoded = b"z"
    decoded = ascii85decode(encoded)
    assert decoded == b"\x00\x00\x00\x00"


def test_ascii85decode_partial_group():
    encoded = b"9jqo^BlbD-BleB1DJ+*+F(f,q"  # Encodes 'Man is distinguished'
    decoded = ascii85decode(encoded + b"~>")
    assert decoded.startswith(b"Man is distinguished")


def test_ascii85decode_with_termination():
    encoded = b"9jqo^~>"
    decoded = ascii85decode(encoded)
    assert decoded == b"Man "


def test_asciihexdecode_basic():
    encoded = b"48656C6C6F>"
    decoded = asciihexdecode(encoded)
    assert decoded == b"Hello"


def test_asciihexdecode_with_whitespace():
    encoded = b"48 65 6C 6C 6F >"
    decoded = asciihexdecode(encoded)
    assert decoded == b"Hello"


def test_asciihexdecode_odd_length():
    encoded = b"48656C6C6F3"
    decoded = asciihexdecode(encoded)
    assert decoded == b"Hello0"


def test_asciihexdecode_empty():
    encoded = b""
    decoded = asciihexdecode(encoded)
    assert decoded == b""


def test_asciihexdecode_invalid_characters():
    encoded = b"ZZ>"
    with pytest.raises(ValueError):
        asciihexdecode(encoded)

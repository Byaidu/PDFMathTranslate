import pytest
from pdf2zh.encodingdb import name2unicode, EncodingDB, PDFKeyError
from pdf2zh.psparser import PSLiteral


def test_name2unicode_basic():
    assert name2unicode("A") == "A"
    assert name2unicode("dollar") == "$"


def test_name2unicode_composite():
    assert name2unicode("A_B") == "AB"
    assert name2unicode("A_B_C") == "ABC"


def test_name2unicode_uni():
    assert name2unicode("uni0041") == "A"  # Unicode A
    assert name2unicode("uni00410042") == "AB"  # Unicode AB


def test_name2unicode_u():
    assert name2unicode("u0041") == "A"  # Unicode A
    assert name2unicode("u1F600") == "😀"  # Unicode emoji


def test_name2unicode_invalid_type():
    with pytest.raises(PDFKeyError):
        name2unicode(123)  # type: ignore


def test_name2unicode_invalid_name():
    with pytest.raises(PDFKeyError):
        name2unicode("invalid_name")


def test_name2unicode_invalid_unicode():
    with pytest.raises(PDFKeyError):
        name2unicode("uniD800")  # Surrogate pair range


def test_encoding_db_basic():
    assert "StandardEncoding" in EncodingDB.encodings
    assert "MacRomanEncoding" in EncodingDB.encodings
    assert "WinAnsiEncoding" in EncodingDB.encodings
    assert "PDFDocEncoding" in EncodingDB.encodings


def test_encoding_db_get_encoding():
    encoding = EncodingDB.get_encoding("StandardEncoding")
    assert isinstance(encoding, dict)
    assert 65 in encoding  # ASCII 'A'


def test_encoding_db_get_encoding_with_diff():
    diff = [0, PSLiteral("A"), PSLiteral("B")]
    encoding = EncodingDB.get_encoding("StandardEncoding", diff)
    assert encoding[0] == "A"
    assert encoding[1] == "B"


def test_encoding_db_get_encoding_invalid():
    # Should return StandardEncoding for invalid encoding name
    encoding = EncodingDB.get_encoding("InvalidEncoding")
    assert encoding == EncodingDB.std2unicode

import pytest

from pdf2zh.cmapdb import (
    CMapBase,
    CMap,
    IdentityCMap,
    IdentityCMapByte,
    UnicodeMap,
    IdentityUnicodeMap,
    FileCMap,
    FileUnicodeMap,
    PSLiteral,
    PDFTypeError,
)


def test_cmap_base():
    cmap = CMapBase(WMode=0, Name="TestMap")
    assert cmap.attrs["WMode"] == 0
    assert cmap.attrs["Name"] == "TestMap"
    assert not cmap.is_vertical()

    cmap.set_attr("WMode", 1)
    assert cmap.is_vertical()


def test_cmap():
    cmap = CMap(CMapName="TestCMap")
    assert repr(cmap) == "<CMap: TestCMap>"

    # Test code2cid mapping
    cmap.code2cid = {1: 100, 2: {3: 200}}
    decoded = list(cmap.decode(bytes([1])))
    assert decoded == [100]

    decoded = list(cmap.decode(bytes([2, 3])))
    assert decoded == [200]


def test_cmap_use_cmap():
    cmap1 = CMap()
    cmap1.code2cid = {1: 100, 2: {3: 200}}

    cmap2 = CMap()
    cmap2.use_cmap(cmap1)
    assert cmap2.code2cid == {1: 100, 2: {3: 200}}


def test_identity_cmap():
    cmap = IdentityCMap()
    result = cmap.decode(b"\x00\x01\x00\x02")
    assert result == (1, 2)

    # Test empty input
    assert cmap.decode(b"") == ()


def test_identity_cmap_byte():
    cmap = IdentityCMapByte()
    result = cmap.decode(b"\x01\x02\x03")
    assert result == (1, 2, 3)

    # Test empty input
    assert cmap.decode(b"") == ()


def test_unicode_map():
    umap = UnicodeMap(CMapName="TestUnicode")
    assert repr(umap) == "<UnicodeMap: TestUnicode>"

    umap.cid2unichr[100] = "A"
    assert umap.get_unichr(100) == "A"


def test_identity_unicode_map():
    umap = IdentityUnicodeMap()
    assert umap.get_unichr(65) == "A"  # ASCII 65 = 'A'
    assert umap.get_unichr(0x4E00) == "一"  # CJK Unified Ideograph


def test_file_cmap():
    cmap = FileCMap()
    cmap.add_code2cid("AB", 100)

    result = list(cmap.decode(bytes([ord("A"), ord("B")])))
    assert result == [100]


def test_file_unicode_map():
    umap = FileUnicodeMap()

    # Test with PSLiteral
    umap.add_cid2unichr(100, PSLiteral("A"))
    assert umap.get_unichr(100) == "A"

    # Test with bytes (UTF-16BE)
    umap.add_cid2unichr(101, b"\x00A")
    assert umap.get_unichr(101) == "A"

    # Test with integer
    umap.add_cid2unichr(102, 65)  # ASCII 65 = 'A'
    assert umap.get_unichr(102) == "A"

    # Test invalid input
    with pytest.raises(PDFTypeError):
        umap.add_cid2unichr(103, 1.5)  # type: ignore


def test_file_unicode_map_space_handling():
    umap = FileUnicodeMap()

    # Add regular space
    umap.add_cid2unichr(100, 32)  # space character
    assert umap.get_unichr(100) == " "

    # Try to add non-breaking space - should be ignored
    umap.add_cid2unichr(100, 0xA0)  # non-breaking space
    assert umap.get_unichr(100) == " "  # should still be regular space

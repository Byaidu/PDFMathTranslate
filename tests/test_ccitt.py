import pytest
from pdf2zh.ccitt import BitParser, CCITTG4Parser, CCITTFaxDecoder, ccittfaxdecode


class TestBitParser:
    def test_init(self):
        parser = BitParser()
        assert parser._pos == 0

    def test_add_bits(self):
        root = [None, None]
        BitParser.add(root, 1, "1")
        assert root[1] == 1
        assert root[0] is None

    def test_feedbytes_simple(self):
        parser = BitParser()
        parser._state = [None, None]
        parser._accept = lambda x: [None, None]
        parser.feedbytes(b"\x80")  # 10000000
        assert parser._pos == 8


class TestCCITTG4Parser:
    def test_init(self):
        parser = CCITTG4Parser(width=8)
        assert parser.width == 8
        assert parser.bytealign is False
        assert len(parser._curline) == 8

    def test_mode_parsing(self):
        parser = CCITTG4Parser(width=8)
        # Test pass mode
        new_state = parser._parse_mode("p")
        assert new_state == parser.MODE

        # Test horizontal mode
        new_state = parser._parse_mode("h")
        assert new_state in (parser.WHITE, parser.BLACK)

    def test_vertical_coding(self):
        parser = CCITTG4Parser(width=8)
        parser._curpos = 0
        parser._color = 1
        parser._do_vertical(0)  # No offset
        assert parser._curpos >= 0

    @pytest.mark.parametrize("n1,n2", [(1, 1), (2, 2), (3, 3)])
    def test_horizontal_coding(self, n1, n2):
        parser = CCITTG4Parser(width=8)
        parser._curpos = 0
        parser._color = 1
        parser._do_horizontal(n1, n2)
        assert parser._curpos == n1 + n2


class TestCCITTFaxDecoder:
    def test_init(self):
        decoder = CCITTFaxDecoder(width=8)
        assert decoder.width == 8
        assert decoder.reversed is False
        assert decoder._buf == b""

    def test_decode_empty(self):
        decoder = CCITTFaxDecoder(width=8)
        result = decoder.close()
        assert result == b""

    def test_basic_decoding(self):
        decoder = CCITTFaxDecoder(width=8)
        decoder.feedbytes(b"\x00")
        result = decoder.close()
        assert isinstance(result, bytes)


def test_ccittfaxdecode():
    params = {"K": -1, "Columns": 8, "EncodedByteAlign": False, "BlackIs1": False}
    result = ccittfaxdecode(b"\x00", params)
    assert isinstance(result, bytes)

    with pytest.raises(Exception):
        ccittfaxdecode(b"\x00", {"K": 0})  # Should raise for unsupported K value


@pytest.fixture
def basic_parser():
    return CCITTG4Parser(width=8)


class TestErrorHandling:
    def test_invalid_mode(self, basic_parser):
        with pytest.raises(CCITTG4Parser.InvalidData):
            basic_parser._parse_mode("invalid")

    def test_eofb_detection(self, basic_parser):
        with pytest.raises(CCITTG4Parser.EOFB):
            basic_parser._parse_mode("e")

    def test_byte_alignment(self):
        parser = CCITTG4Parser(width=8, bytealign=True)
        parser._curpos = 8  # Simulate end of line
        with pytest.raises(CCITTG4Parser.ByteSkip):
            parser._flush_line()

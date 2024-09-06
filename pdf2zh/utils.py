"""Miscellaneous Routines."""

import io
import pathlib
import string
import struct
from html import escape
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    TextIO,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from pdf2zh.pdfexceptions import PDFTypeError, PDFValueError

if TYPE_CHECKING:
    from pdf2zh.layout import LTComponent

import charset_normalizer  # For str encoding detection

# from sys import maxint as INF doesn't work anymore under Python3, but PDF
# still uses 32 bits ints
INF = (1 << 31) - 1


FileOrName = Union[pathlib.PurePath, str, io.IOBase]
AnyIO = Union[TextIO, BinaryIO]


class open_filename:
    """Context manager that allows opening a filename
    (str or pathlib.PurePath type is supported) and closes it on exit,
    (just like `open`), but does nothing for file-like objects.
    """

    def __init__(self, filename: FileOrName, *args: Any, **kwargs: Any) -> None:
        if isinstance(filename, pathlib.PurePath):
            filename = str(filename)
        if isinstance(filename, str):
            self.file_handler: AnyIO = open(filename, *args, **kwargs)
            self.closing = True
        elif isinstance(filename, io.IOBase):
            self.file_handler = cast(AnyIO, filename)
            self.closing = False
        else:
            raise PDFTypeError("Unsupported input type: %s" % type(filename))

    def __enter__(self) -> AnyIO:
        return self.file_handler

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self.closing:
            self.file_handler.close()


def make_compat_bytes(in_str: str) -> bytes:
    """Converts to bytes, encoding to unicode."""
    assert isinstance(in_str, str), str(type(in_str))
    return in_str.encode()


def make_compat_str(o: object) -> str:
    """Converts everything to string, if bytes guessing the encoding."""
    if isinstance(o, bytes):
        enc = charset_normalizer.detect(o)
        try:
            return o.decode(enc["encoding"])
        except UnicodeDecodeError:
            return str(o)
    else:
        return str(o)


def shorten_str(s: str, size: int) -> str:
    if size < 7:
        return s[:size]
    if len(s) > size:
        length = (size - 5) // 2
        return f"{s[:length]} ... {s[-length:]}"
    else:
        return s


def compatible_encode_method(
    bytesorstring: Union[bytes, str],
    encoding: str = "utf-8",
    erraction: str = "ignore",
) -> str:
    """When Py2 str.encode is called, it often means bytes.encode in Py3.

    This does either.
    """
    if isinstance(bytesorstring, str):
        return bytesorstring
    assert isinstance(bytesorstring, bytes), str(type(bytesorstring))
    return bytesorstring.decode(encoding, erraction)


def paeth_predictor(left: int, above: int, upper_left: int) -> int:
    # From http://www.libpng.org/pub/png/spec/1.2/PNG-Filters.html
    # Initial estimate
    p = left + above - upper_left
    # Distances to a,b,c
    pa = abs(p - left)
    pb = abs(p - above)
    pc = abs(p - upper_left)

    # Return nearest of a,b,c breaking ties in order a,b,c
    if pa <= pb and pa <= pc:
        return left
    elif pb <= pc:
        return above
    else:
        return upper_left


def apply_png_predictor(
    pred: int,
    colors: int,
    columns: int,
    bitspercomponent: int,
    data: bytes,
) -> bytes:
    """Reverse the effect of the PNG predictor

    Documentation: http://www.libpng.org/pub/png/spec/1.2/PNG-Filters.html
    """
    if bitspercomponent not in [8, 1]:
        msg = "Unsupported `bitspercomponent': %d" % bitspercomponent
        raise PDFValueError(msg)

    nbytes = colors * columns * bitspercomponent // 8
    bpp = colors * bitspercomponent // 8  # number of bytes per complete pixel
    buf = []
    line_above = list(b"\x00" * columns)
    for scanline_i in range(0, len(data), nbytes + 1):
        filter_type = data[scanline_i]
        line_encoded = data[scanline_i + 1 : scanline_i + 1 + nbytes]
        raw = []

        if filter_type == 0:
            # Filter type 0: None
            raw = list(line_encoded)

        elif filter_type == 1:
            # Filter type 1: Sub
            # To reverse the effect of the Sub() filter after decompression,
            # output the following value:
            #   Raw(x) = Sub(x) + Raw(x - bpp)
            # (computed mod 256), where Raw() refers to the bytes already
            #  decoded.
            for j, sub_x in enumerate(line_encoded):
                if j - bpp < 0:
                    raw_x_bpp = 0
                else:
                    raw_x_bpp = int(raw[j - bpp])
                raw_x = (sub_x + raw_x_bpp) & 255
                raw.append(raw_x)

        elif filter_type == 2:
            # Filter type 2: Up
            # To reverse the effect of the Up() filter after decompression,
            # output the following value:
            #   Raw(x) = Up(x) + Prior(x)
            # (computed mod 256), where Prior() refers to the decoded bytes of
            # the prior scanline.
            for up_x, prior_x in zip(line_encoded, line_above):
                raw_x = (up_x + prior_x) & 255
                raw.append(raw_x)

        elif filter_type == 3:
            # Filter type 3: Average
            # To reverse the effect of the Average() filter after
            # decompression, output the following value:
            #    Raw(x) = Average(x) + floor((Raw(x-bpp)+Prior(x))/2)
            # where the result is computed mod 256, but the prediction is
            # calculated in the same way as for encoding. Raw() refers to the
            # bytes already decoded, and Prior() refers to the decoded bytes of
            # the prior scanline.
            for j, average_x in enumerate(line_encoded):
                if j - bpp < 0:
                    raw_x_bpp = 0
                else:
                    raw_x_bpp = int(raw[j - bpp])
                prior_x = int(line_above[j])
                raw_x = (average_x + (raw_x_bpp + prior_x) // 2) & 255
                raw.append(raw_x)

        elif filter_type == 4:
            # Filter type 4: Paeth
            # To reverse the effect of the Paeth() filter after decompression,
            # output the following value:
            #    Raw(x) = Paeth(x)
            #             + PaethPredictor(Raw(x-bpp), Prior(x), Prior(x-bpp))
            # (computed mod 256), where Raw() and Prior() refer to bytes
            # already decoded. Exactly the same PaethPredictor() function is
            # used by both encoder and decoder.
            for j, paeth_x in enumerate(line_encoded):
                if j - bpp < 0:
                    raw_x_bpp = 0
                    prior_x_bpp = 0
                else:
                    raw_x_bpp = int(raw[j - bpp])
                    prior_x_bpp = int(line_above[j - bpp])
                prior_x = int(line_above[j])
                paeth = paeth_predictor(raw_x_bpp, prior_x, prior_x_bpp)
                raw_x = (paeth_x + paeth) & 255
                raw.append(raw_x)

        else:
            raise PDFValueError("Unsupported predictor value: %d" % filter_type)

        buf.extend(raw)
        line_above = raw
    return bytes(buf)


Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]
Matrix = Tuple[float, float, float, float, float, float]
PathSegment = Union[
    Tuple[str],  # Literal['h']
    Tuple[str, float, float],  # Literal['m', 'l']
    Tuple[str, float, float, float, float],  # Literal['v', 'y']
    Tuple[str, float, float, float, float, float, float],
]  # Literal['c']

#  Matrix operations
MATRIX_IDENTITY: Matrix = (1, 0, 0, 1, 0, 0)


def parse_rect(o: Any) -> Rect:
    try:
        (x0, y0, x1, y1) = o
        return float(x0), float(y0), float(x1), float(y1)
    except ValueError:
        raise PDFValueError("Could not parse rectangle")


def mult_matrix(m1: Matrix, m0: Matrix) -> Matrix:
    (a1, b1, c1, d1, e1, f1) = m1
    (a0, b0, c0, d0, e0, f0) = m0
    """Returns the multiplication of two matrices."""
    return (
        a0 * a1 + c0 * b1,
        b0 * a1 + d0 * b1,
        a0 * c1 + c0 * d1,
        b0 * c1 + d0 * d1,
        a0 * e1 + c0 * f1 + e0,
        b0 * e1 + d0 * f1 + f0,
    )


def translate_matrix(m: Matrix, v: Point) -> Matrix:
    """Translates a matrix by (x, y)."""
    (a, b, c, d, e, f) = m
    (x, y) = v
    return a, b, c, d, x * a + y * c + e, x * b + y * d + f


def apply_matrix_pt(m: Matrix, v: Point) -> Point:
    (a, b, c, d, e, f) = m
    (x, y) = v
    """Applies a matrix to a point."""
    return a * x + c * y + e, b * x + d * y + f


def apply_matrix_norm(m: Matrix, v: Point) -> Point:
    """Equivalent to apply_matrix_pt(M, (p,q)) - apply_matrix_pt(M, (0,0))"""
    (a, b, c, d, e, f) = m
    (p, q) = v
    return a * p + c * q, b * p + d * q


#  Utility functions


def isnumber(x: object) -> bool:
    return isinstance(x, (int, float))


_T = TypeVar("_T")


def uniq(objs: Iterable[_T]) -> Iterator[_T]:
    """Eliminates duplicated elements."""
    done = set()
    for obj in objs:
        if obj in done:
            continue
        done.add(obj)
        yield obj


def fsplit(pred: Callable[[_T], bool], objs: Iterable[_T]) -> Tuple[List[_T], List[_T]]:
    """Split a list into two classes according to the predicate."""
    t = []
    f = []
    for obj in objs:
        if pred(obj):
            t.append(obj)
        else:
            f.append(obj)
    return t, f


def drange(v0: float, v1: float, d: int) -> range:
    """Returns a discrete range."""
    return range(int(v0) // d, int(v1 + d) // d)


def get_bound(pts: Iterable[Point]) -> Rect:
    """Compute a minimal rectangle that covers all the points."""
    limit: Rect = (INF, INF, -INF, -INF)
    (x0, y0, x1, y1) = limit
    for x, y in pts:
        x0 = min(x0, x)
        y0 = min(y0, y)
        x1 = max(x1, x)
        y1 = max(y1, y)
    return x0, y0, x1, y1


def pick(
    seq: Iterable[_T],
    func: Callable[[_T], float],
    maxobj: Optional[_T] = None,
) -> Optional[_T]:
    """Picks the object obj where func(obj) has the highest value."""
    maxscore = None
    for obj in seq:
        score = func(obj)
        if maxscore is None or maxscore < score:
            (maxscore, maxobj) = (score, obj)
    return maxobj


def choplist(n: int, seq: Iterable[_T]) -> Iterator[Tuple[_T, ...]]:
    """Groups every n elements of the list."""
    r = []
    for x in seq:
        r.append(x)
        if len(r) == n:
            yield tuple(r)
            r = []


def nunpack(s: bytes, default: int = 0) -> int:
    """Unpacks 1 to 4 or 8 byte integers (big endian)."""
    length = len(s)
    if not length:
        return default
    elif length == 1:
        return ord(s)
    elif length == 2:
        return cast(int, struct.unpack(">H", s)[0])
    elif length == 3:
        return cast(int, struct.unpack(">L", b"\x00" + s)[0])
    elif length == 4:
        return cast(int, struct.unpack(">L", s)[0])
    elif length == 8:
        return cast(int, struct.unpack(">Q", s)[0])
    else:
        raise PDFTypeError("invalid length: %d" % length)


PDFDocEncoding = "".join(
    chr(x)
    for x in (
        0x0000,
        0x0001,
        0x0002,
        0x0003,
        0x0004,
        0x0005,
        0x0006,
        0x0007,
        0x0008,
        0x0009,
        0x000A,
        0x000B,
        0x000C,
        0x000D,
        0x000E,
        0x000F,
        0x0010,
        0x0011,
        0x0012,
        0x0013,
        0x0014,
        0x0015,
        0x0017,
        0x0017,
        0x02D8,
        0x02C7,
        0x02C6,
        0x02D9,
        0x02DD,
        0x02DB,
        0x02DA,
        0x02DC,
        0x0020,
        0x0021,
        0x0022,
        0x0023,
        0x0024,
        0x0025,
        0x0026,
        0x0027,
        0x0028,
        0x0029,
        0x002A,
        0x002B,
        0x002C,
        0x002D,
        0x002E,
        0x002F,
        0x0030,
        0x0031,
        0x0032,
        0x0033,
        0x0034,
        0x0035,
        0x0036,
        0x0037,
        0x0038,
        0x0039,
        0x003A,
        0x003B,
        0x003C,
        0x003D,
        0x003E,
        0x003F,
        0x0040,
        0x0041,
        0x0042,
        0x0043,
        0x0044,
        0x0045,
        0x0046,
        0x0047,
        0x0048,
        0x0049,
        0x004A,
        0x004B,
        0x004C,
        0x004D,
        0x004E,
        0x004F,
        0x0050,
        0x0051,
        0x0052,
        0x0053,
        0x0054,
        0x0055,
        0x0056,
        0x0057,
        0x0058,
        0x0059,
        0x005A,
        0x005B,
        0x005C,
        0x005D,
        0x005E,
        0x005F,
        0x0060,
        0x0061,
        0x0062,
        0x0063,
        0x0064,
        0x0065,
        0x0066,
        0x0067,
        0x0068,
        0x0069,
        0x006A,
        0x006B,
        0x006C,
        0x006D,
        0x006E,
        0x006F,
        0x0070,
        0x0071,
        0x0072,
        0x0073,
        0x0074,
        0x0075,
        0x0076,
        0x0077,
        0x0078,
        0x0079,
        0x007A,
        0x007B,
        0x007C,
        0x007D,
        0x007E,
        0x0000,
        0x2022,
        0x2020,
        0x2021,
        0x2026,
        0x2014,
        0x2013,
        0x0192,
        0x2044,
        0x2039,
        0x203A,
        0x2212,
        0x2030,
        0x201E,
        0x201C,
        0x201D,
        0x2018,
        0x2019,
        0x201A,
        0x2122,
        0xFB01,
        0xFB02,
        0x0141,
        0x0152,
        0x0160,
        0x0178,
        0x017D,
        0x0131,
        0x0142,
        0x0153,
        0x0161,
        0x017E,
        0x0000,
        0x20AC,
        0x00A1,
        0x00A2,
        0x00A3,
        0x00A4,
        0x00A5,
        0x00A6,
        0x00A7,
        0x00A8,
        0x00A9,
        0x00AA,
        0x00AB,
        0x00AC,
        0x0000,
        0x00AE,
        0x00AF,
        0x00B0,
        0x00B1,
        0x00B2,
        0x00B3,
        0x00B4,
        0x00B5,
        0x00B6,
        0x00B7,
        0x00B8,
        0x00B9,
        0x00BA,
        0x00BB,
        0x00BC,
        0x00BD,
        0x00BE,
        0x00BF,
        0x00C0,
        0x00C1,
        0x00C2,
        0x00C3,
        0x00C4,
        0x00C5,
        0x00C6,
        0x00C7,
        0x00C8,
        0x00C9,
        0x00CA,
        0x00CB,
        0x00CC,
        0x00CD,
        0x00CE,
        0x00CF,
        0x00D0,
        0x00D1,
        0x00D2,
        0x00D3,
        0x00D4,
        0x00D5,
        0x00D6,
        0x00D7,
        0x00D8,
        0x00D9,
        0x00DA,
        0x00DB,
        0x00DC,
        0x00DD,
        0x00DE,
        0x00DF,
        0x00E0,
        0x00E1,
        0x00E2,
        0x00E3,
        0x00E4,
        0x00E5,
        0x00E6,
        0x00E7,
        0x00E8,
        0x00E9,
        0x00EA,
        0x00EB,
        0x00EC,
        0x00ED,
        0x00EE,
        0x00EF,
        0x00F0,
        0x00F1,
        0x00F2,
        0x00F3,
        0x00F4,
        0x00F5,
        0x00F6,
        0x00F7,
        0x00F8,
        0x00F9,
        0x00FA,
        0x00FB,
        0x00FC,
        0x00FD,
        0x00FE,
        0x00FF,
    )
)


def decode_text(s: bytes) -> str:
    """Decodes a PDFDocEncoding string to Unicode."""
    if s.startswith(b"\xfe\xff"):
        return str(s[2:], "utf-16be", "ignore")
    else:
        return "".join(PDFDocEncoding[c] for c in s)


def enc(x: str) -> str:
    """Encodes a string for SGML/XML/HTML"""
    if isinstance(x, bytes):
        return ""
    return escape(x)


def bbox2str(bbox: Rect) -> str:
    (x0, y0, x1, y1) = bbox
    return f"{x0:.3f},{y0:.3f},{x1:.3f},{y1:.3f}"


def matrix2str(m: Matrix) -> str:
    (a, b, c, d, e, f) = m
    return f"[{a:.2f},{b:.2f},{c:.2f},{d:.2f}, ({e:.2f},{f:.2f})]"


def vecBetweenBoxes(obj1: "LTComponent", obj2: "LTComponent") -> Point:
    """A distance function between two TextBoxes.

    Consider the bounding rectangle for obj1 and obj2.
    Return vector between 2 boxes boundaries if they don't overlap, otherwise
    returns vector betweeen boxes centers

             +------+..........+ (x1, y1)
             | obj1 |          :
             +------+www+------+
             :          | obj2 |
    (x0, y0) +..........+------+
    """
    (x0, y0) = (min(obj1.x0, obj2.x0), min(obj1.y0, obj2.y0))
    (x1, y1) = (max(obj1.x1, obj2.x1), max(obj1.y1, obj2.y1))
    (ow, oh) = (x1 - x0, y1 - y0)
    (iw, ih) = (ow - obj1.width - obj2.width, oh - obj1.height - obj2.height)
    if iw < 0 and ih < 0:
        # if one is inside another we compute euclidean distance
        (xc1, yc1) = ((obj1.x0 + obj1.x1) / 2, (obj1.y0 + obj1.y1) / 2)
        (xc2, yc2) = ((obj2.x0 + obj2.x1) / 2, (obj2.y0 + obj2.y1) / 2)
        return xc1 - xc2, yc1 - yc2
    else:
        return max(0, iw), max(0, ih)


LTComponentT = TypeVar("LTComponentT", bound="LTComponent")


class Plane(Generic[LTComponentT]):
    """A set-like data structure for objects placed on a plane.

    Can efficiently find objects in a certain rectangular area.
    It maintains two parallel lists of objects, each of
    which is sorted by its x or y coordinate.
    """

    def __init__(self, bbox: Rect, gridsize: int = 50) -> None:
        self._seq: List[LTComponentT] = []  # preserve the object order.
        self._objs: Set[LTComponentT] = set()
        self._grid: Dict[Point, List[LTComponentT]] = {}
        self.gridsize = gridsize
        (self.x0, self.y0, self.x1, self.y1) = bbox

    def __repr__(self) -> str:
        return "<Plane objs=%r>" % list(self)

    def __iter__(self) -> Iterator[LTComponentT]:
        return (obj for obj in self._seq if obj in self._objs)

    def __len__(self) -> int:
        return len(self._objs)

    def __contains__(self, obj: object) -> bool:
        return obj in self._objs

    def _getrange(self, bbox: Rect) -> Iterator[Point]:
        (x0, y0, x1, y1) = bbox
        if x1 <= self.x0 or self.x1 <= x0 or y1 <= self.y0 or self.y1 <= y0:
            return
        x0 = max(self.x0, x0)
        y0 = max(self.y0, y0)
        x1 = min(self.x1, x1)
        y1 = min(self.y1, y1)
        for grid_y in drange(y0, y1, self.gridsize):
            for grid_x in drange(x0, x1, self.gridsize):
                yield (grid_x, grid_y)

    def extend(self, objs: Iterable[LTComponentT]) -> None:
        for obj in objs:
            self.add(obj)

    def add(self, obj: LTComponentT) -> None:
        """Place an object."""
        for k in self._getrange((obj.x0, obj.y0, obj.x1, obj.y1)):
            if k not in self._grid:
                r: List[LTComponentT] = []
                self._grid[k] = r
            else:
                r = self._grid[k]
            r.append(obj)
        self._seq.append(obj)
        self._objs.add(obj)

    def remove(self, obj: LTComponentT) -> None:
        """Displace an object."""
        for k in self._getrange((obj.x0, obj.y0, obj.x1, obj.y1)):
            try:
                self._grid[k].remove(obj)
            except (KeyError, ValueError):
                pass
        self._objs.remove(obj)

    def find(self, bbox: Rect) -> Iterator[LTComponentT]:
        """Finds objects that are in a certain area."""
        (x0, y0, x1, y1) = bbox
        done = set()
        for k in self._getrange(bbox):
            if k not in self._grid:
                continue
            for obj in self._grid[k]:
                if obj in done:
                    continue
                done.add(obj)
                if obj.x1 <= x0 or x1 <= obj.x0 or obj.y1 <= y0 or y1 <= obj.y0:
                    continue
                yield obj


ROMAN_ONES = ["i", "x", "c", "m"]
ROMAN_FIVES = ["v", "l", "d"]


def format_int_roman(value: int) -> str:
    """Format a number as lowercase Roman numerals."""
    assert 0 < value < 4000
    result: List[str] = []
    index = 0

    while value != 0:
        value, remainder = divmod(value, 10)
        if remainder == 9:
            result.insert(0, ROMAN_ONES[index])
            result.insert(1, ROMAN_ONES[index + 1])
        elif remainder == 4:
            result.insert(0, ROMAN_ONES[index])
            result.insert(1, ROMAN_FIVES[index])
        else:
            over_five = remainder >= 5
            if over_five:
                result.insert(0, ROMAN_FIVES[index])
                remainder -= 5
            result.insert(1 if over_five else 0, ROMAN_ONES[index] * remainder)
        index += 1

    return "".join(result)


def format_int_alpha(value: int) -> str:
    """Format a number as lowercase letters a-z, aa-zz, etc."""
    assert value > 0
    result: List[str] = []

    while value != 0:
        value, remainder = divmod(value - 1, len(string.ascii_lowercase))
        result.append(string.ascii_lowercase[remainder])

    result.reverse()
    return "".join(result)

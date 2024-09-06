"""Adobe character mapping (CMap) support.

CMaps provide the mapping between character codes and Unicode
code-points to character ids (CIDs).

More information is available on:

  https://github.com/adobe-type-tools/cmap-resources

"""

import gzip
import logging
import os
import os.path
import pickle as pickle
import struct
import sys
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    Iterator,
    List,
    MutableMapping,
    Optional,
    Set,
    TextIO,
    Tuple,
    Union,
    cast,
)

from pdf2zh.encodingdb import name2unicode
from pdf2zh.pdfexceptions import PDFException, PDFTypeError
from pdf2zh.psexceptions import PSEOF, PSSyntaxError
from pdf2zh.psparser import KWD, PSKeyword, PSLiteral, PSStackParser, literal_name
from pdf2zh.utils import choplist, nunpack

log = logging.getLogger(__name__)


class CMapError(PDFException):
    pass


class CMapBase:
    debug = 0

    def __init__(self, **kwargs: object) -> None:
        self.attrs: MutableMapping[str, object] = kwargs.copy()

    def is_vertical(self) -> bool:
        return self.attrs.get("WMode", 0) != 0

    def set_attr(self, k: str, v: object) -> None:
        self.attrs[k] = v

    def add_code2cid(self, code: str, cid: int) -> None:
        pass

    def add_cid2unichr(self, cid: int, code: Union[PSLiteral, bytes, int]) -> None:
        pass

    def use_cmap(self, cmap: "CMapBase") -> None:
        pass

    def decode(self, code: bytes) -> Iterable[int]:
        raise NotImplementedError


class CMap(CMapBase):
    def __init__(self, **kwargs: Union[str, int]) -> None:
        CMapBase.__init__(self, **kwargs)
        self.code2cid: Dict[int, object] = {}

    def __repr__(self) -> str:
        return "<CMap: %s>" % self.attrs.get("CMapName")

    def use_cmap(self, cmap: CMapBase) -> None:
        assert isinstance(cmap, CMap), str(type(cmap))

        def copy(dst: Dict[int, object], src: Dict[int, object]) -> None:
            for k, v in src.items():
                if isinstance(v, dict):
                    d: Dict[int, object] = {}
                    dst[k] = d
                    copy(d, v)
                else:
                    dst[k] = v

        copy(self.code2cid, cmap.code2cid)

    def decode(self, code: bytes) -> Iterator[int]:
        # log.debug("decode: %r, %r", self, code)
        d = self.code2cid
        for i in iter(code):
            if i in d:
                x = d[i]
                if isinstance(x, int):
                    yield x
                    d = self.code2cid
                else:
                    d = cast(Dict[int, object], x)
            else:
                d = self.code2cid

    def dump(
        self,
        out: TextIO = sys.stdout,
        code2cid: Optional[Dict[int, object]] = None,
        code: Tuple[int, ...] = (),
    ) -> None:
        if code2cid is None:
            code2cid = self.code2cid
            code = ()
        for k, v in sorted(code2cid.items()):
            c = code + (k,)
            if isinstance(v, int):
                out.write("code %r = cid %d\n" % (c, v))
            else:
                self.dump(out=out, code2cid=cast(Dict[int, object], v), code=c)


class IdentityCMap(CMapBase):
    def decode(self, code: bytes) -> Tuple[int, ...]:
        n = len(code) // 2
        if n:
            return struct.unpack(">%dH" % n, code)
        else:
            return ()


class IdentityCMapByte(IdentityCMap):
    def decode(self, code: bytes) -> Tuple[int, ...]:
        n = len(code)
        if n:
            return struct.unpack(">%dB" % n, code)
        else:
            return ()


class UnicodeMap(CMapBase):
    def __init__(self, **kwargs: Union[str, int]) -> None:
        CMapBase.__init__(self, **kwargs)
        self.cid2unichr: Dict[int, str] = {}

    def __repr__(self) -> str:
        return "<UnicodeMap: %s>" % self.attrs.get("CMapName")

    def get_unichr(self, cid: int) -> str:
        # log.debug("get_unichr: %r, %r", self, cid)
        return self.cid2unichr[cid]

    def dump(self, out: TextIO = sys.stdout) -> None:
        for k, v in sorted(self.cid2unichr.items()):
            out.write("cid %d = unicode %r\n" % (k, v))


class IdentityUnicodeMap(UnicodeMap):
    def get_unichr(self, cid: int) -> str:
        """Interpret character id as unicode codepoint"""
        # log.debug("get_unichr: %r, %r", self, cid)
        return chr(cid)


class FileCMap(CMap):
    def add_code2cid(self, code: str, cid: int) -> None:
        assert isinstance(code, str) and isinstance(cid, int), str(
            (type(code), type(cid)),
        )
        d = self.code2cid
        for c in code[:-1]:
            ci = ord(c)
            if ci in d:
                d = cast(Dict[int, object], d[ci])
            else:
                t: Dict[int, object] = {}
                d[ci] = t
                d = t
        ci = ord(code[-1])
        d[ci] = cid


class FileUnicodeMap(UnicodeMap):
    def add_cid2unichr(self, cid: int, code: Union[PSLiteral, bytes, int]) -> None:
        assert isinstance(cid, int), str(type(cid))
        if isinstance(code, PSLiteral):
            # Interpret as an Adobe glyph name.
            assert isinstance(code.name, str)
            unichr = name2unicode(code.name)
        elif isinstance(code, bytes):
            # Interpret as UTF-16BE.
            unichr = code.decode("UTF-16BE", "ignore")
        elif isinstance(code, int):
            unichr = chr(code)
        else:
            raise PDFTypeError(code)

        # A0 = non-breaking space, some weird fonts can have a collision on a cid here.
        if unichr == "\u00a0" and self.cid2unichr.get(cid) == " ":
            return
        self.cid2unichr[cid] = unichr


class PyCMap(CMap):
    def __init__(self, name: str, module: Any) -> None:
        super().__init__(CMapName=name)
        self.code2cid = module.CODE2CID
        if module.IS_VERTICAL:
            self.attrs["WMode"] = 1


class PyUnicodeMap(UnicodeMap):
    def __init__(self, name: str, module: Any, vertical: bool) -> None:
        super().__init__(CMapName=name)
        if vertical:
            self.cid2unichr = module.CID2UNICHR_V
            self.attrs["WMode"] = 1
        else:
            self.cid2unichr = module.CID2UNICHR_H


class CMapDB:
    _cmap_cache: Dict[str, PyCMap] = {}
    _umap_cache: Dict[str, List[PyUnicodeMap]] = {}

    class CMapNotFound(CMapError):
        pass

    @classmethod
    def _load_data(cls, name: str) -> Any:
        name = name.replace("\0", "")
        filename = "%s.pickle.gz" % name
        # log.debug("loading: %r", name)
        cmap_paths = (
            os.environ.get("CMAP_PATH", "/usr/share/pdf2zh/"),
            os.path.join(os.path.dirname(__file__), "cmap"),
        )
        for directory in cmap_paths:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                gzfile = gzip.open(path)
                try:
                    return type(str(name), (), pickle.loads(gzfile.read()))
                finally:
                    gzfile.close()
        raise CMapDB.CMapNotFound(name)

    @classmethod
    def get_cmap(cls, name: str) -> CMapBase:
        if name == "Identity-H":
            return IdentityCMap(WMode=0)
        elif name == "Identity-V":
            return IdentityCMap(WMode=1)
        elif name == "OneByteIdentityH":
            return IdentityCMapByte(WMode=0)
        elif name == "OneByteIdentityV":
            return IdentityCMapByte(WMode=1)
        try:
            return cls._cmap_cache[name]
        except KeyError:
            pass
        data = cls._load_data(name)
        cls._cmap_cache[name] = cmap = PyCMap(name, data)
        return cmap

    @classmethod
    def get_unicode_map(cls, name: str, vertical: bool = False) -> UnicodeMap:
        try:
            return cls._umap_cache[name][vertical]
        except KeyError:
            pass
        data = cls._load_data("to-unicode-%s" % name)
        cls._umap_cache[name] = [PyUnicodeMap(name, data, v) for v in (False, True)]
        return cls._umap_cache[name][vertical]


class CMapParser(PSStackParser[PSKeyword]):
    def __init__(self, cmap: CMapBase, fp: BinaryIO) -> None:
        PSStackParser.__init__(self, fp)
        self.cmap = cmap
        # some ToUnicode maps don't have "begincmap" keyword.
        self._in_cmap = True
        self._warnings: Set[str] = set()

    def run(self) -> None:
        try:
            self.nextobject()
        except PSEOF:
            pass

    KEYWORD_BEGINCMAP = KWD(b"begincmap")
    KEYWORD_ENDCMAP = KWD(b"endcmap")
    KEYWORD_USECMAP = KWD(b"usecmap")
    KEYWORD_DEF = KWD(b"def")
    KEYWORD_BEGINCODESPACERANGE = KWD(b"begincodespacerange")
    KEYWORD_ENDCODESPACERANGE = KWD(b"endcodespacerange")
    KEYWORD_BEGINCIDRANGE = KWD(b"begincidrange")
    KEYWORD_ENDCIDRANGE = KWD(b"endcidrange")
    KEYWORD_BEGINCIDCHAR = KWD(b"begincidchar")
    KEYWORD_ENDCIDCHAR = KWD(b"endcidchar")
    KEYWORD_BEGINBFRANGE = KWD(b"beginbfrange")
    KEYWORD_ENDBFRANGE = KWD(b"endbfrange")
    KEYWORD_BEGINBFCHAR = KWD(b"beginbfchar")
    KEYWORD_ENDBFCHAR = KWD(b"endbfchar")
    KEYWORD_BEGINNOTDEFRANGE = KWD(b"beginnotdefrange")
    KEYWORD_ENDNOTDEFRANGE = KWD(b"endnotdefrange")

    def do_keyword(self, pos: int, token: PSKeyword) -> None:
        """ToUnicode CMaps

        See Section 5.9.2 - ToUnicode CMaps of the PDF Reference.
        """
        if token is self.KEYWORD_BEGINCMAP:
            self._in_cmap = True
            self.popall()
            return

        elif token is self.KEYWORD_ENDCMAP:
            self._in_cmap = False
            return

        if not self._in_cmap:
            return

        if token is self.KEYWORD_DEF:
            try:
                ((_, k), (_, v)) = self.pop(2)
                self.cmap.set_attr(literal_name(k), v)
            except PSSyntaxError:
                pass
            return

        if token is self.KEYWORD_USECMAP:
            try:
                ((_, cmapname),) = self.pop(1)
                self.cmap.use_cmap(CMapDB.get_cmap(literal_name(cmapname)))
            except PSSyntaxError:
                pass
            except CMapDB.CMapNotFound:
                pass
            return

        if token is self.KEYWORD_BEGINCODESPACERANGE:
            self.popall()
            return
        if token is self.KEYWORD_ENDCODESPACERANGE:
            self.popall()
            return

        if token is self.KEYWORD_BEGINCIDRANGE:
            self.popall()
            return

        if token is self.KEYWORD_ENDCIDRANGE:
            objs = [obj for (__, obj) in self.popall()]
            for start_byte, end_byte, cid in choplist(3, objs):
                if not isinstance(start_byte, bytes):
                    self._warn_once("The start object of begincidrange is not a byte.")
                    continue
                if not isinstance(end_byte, bytes):
                    self._warn_once("The end object of begincidrange is not a byte.")
                    continue
                if not isinstance(cid, int):
                    self._warn_once("The cid object of begincidrange is not a byte.")
                    continue
                if len(start_byte) != len(end_byte):
                    self._warn_once(
                        "The start and end byte of begincidrange have "
                        "different lengths.",
                    )
                    continue
                start_prefix = start_byte[:-4]
                end_prefix = end_byte[:-4]
                if start_prefix != end_prefix:
                    self._warn_once(
                        "The prefix of the start and end byte of "
                        "begincidrange are not the same.",
                    )
                    continue
                svar = start_byte[-4:]
                evar = end_byte[-4:]
                start = nunpack(svar)
                end = nunpack(evar)
                vlen = len(svar)
                for i in range(end - start + 1):
                    x = start_prefix + struct.pack(">L", start + i)[-vlen:]
                    self.cmap.add_cid2unichr(cid + i, x)
            return

        if token is self.KEYWORD_BEGINCIDCHAR:
            self.popall()
            return

        if token is self.KEYWORD_ENDCIDCHAR:
            objs = [obj for (__, obj) in self.popall()]
            for cid, code in choplist(2, objs):
                if isinstance(code, bytes) and isinstance(cid, int):
                    self.cmap.add_cid2unichr(cid, code)
            return

        if token is self.KEYWORD_BEGINBFRANGE:
            self.popall()
            return

        if token is self.KEYWORD_ENDBFRANGE:
            objs = [obj for (__, obj) in self.popall()]
            for start_byte, end_byte, code in choplist(3, objs):
                if not isinstance(start_byte, bytes):
                    self._warn_once("The start object is not a byte.")
                    continue
                if not isinstance(end_byte, bytes):
                    self._warn_once("The end object is not a byte.")
                    continue
                if len(start_byte) != len(end_byte):
                    self._warn_once("The start and end byte have different lengths.")
                    continue
                start = nunpack(start_byte)
                end = nunpack(end_byte)
                if isinstance(code, list):
                    if len(code) != end - start + 1:
                        self._warn_once(
                            "The difference between the start and end "
                            "offsets does not match the code length.",
                        )
                    for cid, unicode_value in zip(range(start, end + 1), code):
                        self.cmap.add_cid2unichr(cid, unicode_value)
                else:
                    assert isinstance(code, bytes)
                    var = code[-4:]
                    base = nunpack(var)
                    prefix = code[:-4]
                    vlen = len(var)
                    for i in range(end - start + 1):
                        x = prefix + struct.pack(">L", base + i)[-vlen:]
                        self.cmap.add_cid2unichr(start + i, x)
            return

        if token is self.KEYWORD_BEGINBFCHAR:
            self.popall()
            return

        if token is self.KEYWORD_ENDBFCHAR:
            objs = [obj for (__, obj) in self.popall()]
            for cid, code in choplist(2, objs):
                if isinstance(cid, bytes) and isinstance(code, bytes):
                    self.cmap.add_cid2unichr(nunpack(cid), code)
            return

        if token is self.KEYWORD_BEGINNOTDEFRANGE:
            self.popall()
            return

        if token is self.KEYWORD_ENDNOTDEFRANGE:
            self.popall()
            return

        self.push((pos, token))

    def _warn_once(self, msg: str) -> None:
        """Warn once for each unique message"""
        if msg not in self._warnings:
            self._warnings.add(msg)
            base_msg = (
                "Ignoring (part of) ToUnicode map because the PDF data "
                "does not conform to the format. This could result in "
                "(cid) values in the output. "
            )
            log.warning(base_msg + msg)

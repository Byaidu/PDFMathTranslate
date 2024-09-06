from pdf2zh.psexceptions import PSException


class PDFException(PSException):
    pass


class PDFTypeError(PDFException, TypeError):
    pass


class PDFValueError(PDFException, ValueError):
    pass


class PDFObjectNotFound(PDFException):
    pass


class PDFNotImplementedError(PDFException, NotImplementedError):
    pass


class PDFKeyError(PDFException, KeyError):
    pass


class PDFEOFError(PDFException, EOFError):
    pass


class PDFIOError(PDFException, IOError):
    pass

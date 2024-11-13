"""Functions that can be used for the most common use-cases for pdf2zh.six"""

import logging
import sys
from io import StringIO
from typing import Any, BinaryIO, Container, Iterator, Optional, cast
import tqdm

from pdf2zh.converter import (
    HOCRConverter,
    HTMLConverter,
    PDFPageAggregator,
    TextConverter,
    XMLConverter,
)
from pdf2zh.image import ImageWriter
from pdf2zh.layout import LAParams, LTPage
from pdf2zh.pdfdevice import PDFDevice, TagExtractor
from pdf2zh.pdfexceptions import PDFValueError
from pdf2zh.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdf2zh.pdfpage import PDFPage
from pdf2zh.utils import AnyIO, FileOrName, open_filename
import numpy as np
from pymupdf import Document


def extract_text_to_fp(
    inf: BinaryIO,
    outfp: AnyIO,
    output_type: str = "text",
    codec: str = "utf-8",
    laparams: Optional[LAParams] = None,
    maxpages: int = 0,
    pages: Optional[Container[int]] = None,
    password: str = "",
    scale: float = 1.0,
    rotation: int = 0,
    layoutmode: str = "normal",
    output_dir: Optional[str] = None,
    strip_control: bool = False,
    debug: bool = False,
    disable_caching: bool = False,
    page_count: int = 0,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_en: Document = None,
    model = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    **kwargs: Any,
) -> None:
    """Parses text from inf-file and writes to outfp file-like object.

    Takes loads of optional arguments but the defaults are somewhat sane.
    Beware laparams: Including an empty LAParams is not the same as passing
    None!

    :param inf: a file-like object to read PDF structure from, such as a
        file handler (using the builtin `open()` function) or a `BytesIO`.
    :param outfp: a file-like object to write the text to.
    :param output_type: May be 'text', 'xml', 'html', 'hocr', 'tag'.
        Only 'text' works properly.
    :param codec: Text decoding codec
    :param laparams: An LAParams object from pdf2zh.layout. Default is None
        but may not layout correctly.
    :param maxpages: How many pages to stop parsing after
    :param page_numbers: zero-indexed page numbers to operate on.
    :param password: For encrypted PDFs, the password to decrypt.
    :param scale: Scale factor
    :param rotation: Rotation factor
    :param layoutmode: Default is 'normal', see
        pdf2zh.converter.HTMLConverter
    :param output_dir: If given, creates an ImageWriter for extracted images.
    :param strip_control: Does what it says on the tin
    :param debug: Output more logging data
    :param disable_caching: Does what it says on the tin
    :param other:
    :return: nothing, acting as it does on two streams. Use StringIO to get
        strings.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    imagewriter = None
    if output_dir:
        imagewriter = ImageWriter(output_dir)

    rsrcmgr = PDFResourceManager(caching=not disable_caching)
    device: Optional[PDFDevice] = None
    layout={}

    if output_type != "text" and outfp == sys.stdout:
        outfp = sys.stdout.buffer

    if output_type == "text":
        device = TextConverter(
            rsrcmgr,
            outfp,
            codec=codec,
            laparams=laparams,
            imagewriter=imagewriter,
            vfont=vfont,
            vchar=vchar,
            thread=thread,
            layout=layout,
            lang_in=lang_in,
            lang_out=lang_out,
            service=service,
        )

    elif output_type == "xml":
        device = XMLConverter(
            rsrcmgr,
            outfp,
            codec=codec,
            laparams=laparams,
            imagewriter=imagewriter,
            stripcontrol=strip_control,
        )

    elif output_type == "html":
        device = HTMLConverter(
            rsrcmgr,
            outfp,
            codec=codec,
            scale=scale,
            layoutmode=layoutmode,
            laparams=laparams,
            imagewriter=imagewriter,
        )

    elif output_type == "hocr":
        device = HOCRConverter(
            rsrcmgr,
            outfp,
            codec=codec,
            laparams=laparams,
            stripcontrol=strip_control,
        )

    elif output_type == "tag":
        # Binary I/O is required, but we have no good way to test it here.
        device = TagExtractor(rsrcmgr, cast(BinaryIO, outfp), codec=codec)

    else:
        msg = f"Output type can be text, html, xml or tag but is {output_type}"
        raise PDFValueError(msg)

    assert device is not None
    obj_patch={}
    interpreter = PDFPageInterpreter(rsrcmgr, device, obj_patch)
    if pages:
        total_pages=len(pages)
    else:
        total_pages=page_count
    for page in tqdm.tqdm(PDFPage.get_pages(
        inf,
        pages,
        maxpages=maxpages,
        password=password,
        caching=not disable_caching,
    ), total=total_pages, position=0):
        pix = doc_en[page.pageno].get_pixmap()
        image = np.fromstring(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
        page_layout=model.predict(
            image,
            imgsz=int(pix.height/32)*32,
        )[0]
        # kdtree 是不可能 kdtree 的，不如直接渲染成图片，用空间换时间
        box=np.ones((pix.height, pix.width))
        h,w=box.shape
        vcls=['abandon','figure','table','isolate_formula','formula_caption']
        for i,d in enumerate(page_layout.boxes):
            if not page_layout.names[int(d.cls)] in vcls:
                x0,y0,x1,y1=d.xyxy.squeeze()
                x0,y0,x1,y1=np.clip(int(x0-1),0,w-1),np.clip(int(h-y1-1),0,h-1),np.clip(int(x1+1),0,w-1),np.clip(int(h-y0+1),0,h-1)
                box[y0:y1,x0:x1]=i+2
        for i,d in enumerate(page_layout.boxes):
            if page_layout.names[int(d.cls)] in vcls:
                x0,y0,x1,y1=d.xyxy.squeeze()
                x0,y0,x1,y1=np.clip(int(x0-1),0,w-1),np.clip(int(h-y1-1),0,h-1),np.clip(int(x1+1),0,w-1),np.clip(int(h-y0+1),0,h-1)
                box[y0:y1,x0:x1]=0
        layout[page.pageno]=box
        # print(page.number,page_layout)
        page.rotate = (page.rotate + rotation) % 360
        # 新建一个 xref 存放新指令流
        page.page_xref = doc_en.get_new_xref() # hack
        doc_en.update_object(page.page_xref, "<<>>")
        doc_en.update_stream(page.page_xref,b'')
        doc_en[page.pageno].set_contents(page.page_xref)
        interpreter.process_page(page)

    device.close()
    return obj_patch


def extract_text(
    pdf_file: FileOrName,
    password: str = "",
    page_numbers: Optional[Container[int]] = None,
    maxpages: int = 0,
    caching: bool = True,
    codec: str = "utf-8",
    laparams: Optional[LAParams] = None,
) -> str:
    """Parse and return the text contained in a PDF file.

    :param pdf_file: Either a file path or a file-like object for the PDF file
        to be worked on.
    :param password: For encrypted PDFs, the password to decrypt.
    :param page_numbers: List of zero-indexed page numbers to extract.
    :param maxpages: The maximum number of pages to parse
    :param caching: If resources should be cached
    :param codec: Text decoding codec
    :param laparams: An LAParams object from pdf2zh.layout. If None, uses
        some default settings that often work well.
    :return: a string containing all of the text extracted.
    """
    if laparams is None:
        laparams = LAParams()

    with open_filename(pdf_file, "rb") as fp, StringIO() as output_string:
        fp = cast(BinaryIO, fp)  # we opened in binary mode
        rsrcmgr = PDFResourceManager(caching=caching)
        device = TextConverter(rsrcmgr, output_string, codec=codec, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        for page in PDFPage.get_pages(
            fp,
            page_numbers,
            maxpages=maxpages,
            password=password,
            caching=caching,
        ):
            interpreter.process_page(page)

        return output_string.getvalue()


def extract_pages(
    pdf_file: FileOrName,
    password: str = "",
    page_numbers: Optional[Container[int]] = None,
    maxpages: int = 0,
    caching: bool = True,
    laparams: Optional[LAParams] = None,
) -> Iterator[LTPage]:
    """Extract and yield LTPage objects

    :param pdf_file: Either a file path or a file-like object for the PDF file
        to be worked on.
    :param password: For encrypted PDFs, the password to decrypt.
    :param page_numbers: List of zero-indexed page numbers to extract.
    :param maxpages: The maximum number of pages to parse
    :param caching: If resources should be cached
    :param laparams: An LAParams object from pdf2zh.layout. If None, uses
        some default settings that often work well.
    :return: LTPage objects
    """
    if laparams is None:
        laparams = LAParams()

    with open_filename(pdf_file, "rb") as fp:
        fp = cast(BinaryIO, fp)  # we opened in binary mode
        resource_manager = PDFResourceManager(caching=caching)
        device = PDFPageAggregator(resource_manager, laparams=laparams)
        interpreter = PDFPageInterpreter(resource_manager, device)
        for page in PDFPage.get_pages(
            fp,
            page_numbers,
            maxpages=maxpages,
            password=password,
            caching=caching,
        ):
            interpreter.process_page(page)
            layout = device.get_result()
            yield layout

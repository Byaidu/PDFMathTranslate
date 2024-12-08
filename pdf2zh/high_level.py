"""Functions that can be used for the most common use-cases for pdf2zh.six"""

from typing import BinaryIO
import numpy as np
import tqdm
from pymupdf import Document
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdf2zh.converter import TranslateConverter
from pdf2zh.pdfinterp import PDFPageInterpreterEx
from pymupdf import Font


def extract_text_to_fp(
    inf: BinaryIO,
    pages=None,
    password: str = "",
    debug: bool = False,
    page_count: int = 0,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_en: Document = None,
    model=None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    resfont: str = "",
    noto: Font = None,
    callback: object = None,
    **kwarg,
) -> None:
    rsrcmgr = PDFResourceManager()
    layout = {}
    device = TranslateConverter(
        rsrcmgr, vfont, vchar, thread, layout, lang_in, lang_out, service, resfont, noto
    )

    assert device is not None
    obj_patch = {}
    interpreter = PDFPageInterpreterEx(rsrcmgr, device, obj_patch)
    if pages:
        total_pages = len(pages)
    else:
        total_pages = page_count

    parser = PDFParser(inf)
    doc = PDFDocument(parser, password=password)
    with tqdm.tqdm(total=total_pages) as progress:
        for pageno, page in enumerate(PDFPage.create_pages(doc)):
            if pages and (pageno not in pages):
                continue
            progress.update()
            if callback:
                callback(progress)
            page.pageno = pageno
            pix = doc_en[page.pageno].get_pixmap()
            image = np.fromstring(pix.samples, np.uint8).reshape(
                pix.height, pix.width, 3
            )[:, :, ::-1]
            page_layout = model.predict(image, imgsz=int(pix.height / 32) * 32)[0]
            # kdtree 是不可能 kdtree 的，不如直接渲染成图片，用空间换时间
            box = np.ones((pix.height, pix.width))
            h, w = box.shape
            vcls = ["abandon", "figure", "table", "isolate_formula", "formula_caption"]
            for i, d in enumerate(page_layout.boxes):
                if not page_layout.names[int(d.cls)] in vcls:
                    x0, y0, x1, y1 = d.xyxy.squeeze()
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    box[y0:y1, x0:x1] = i + 2
            for i, d in enumerate(page_layout.boxes):
                if page_layout.names[int(d.cls)] in vcls:
                    x0, y0, x1, y1 = d.xyxy.squeeze()
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    box[y0:y1, x0:x1] = 0
            layout[page.pageno] = box
            # 新建一个 xref 存放新指令流
            page.page_xref = doc_en.get_new_xref()  # hack 插入页面的新 xref
            doc_en.update_object(page.page_xref, "<<>>")
            doc_en.update_stream(page.page_xref, b"")
            doc_en[page.pageno].set_contents(page.page_xref)
            interpreter.process_page(page)

    device.close()
    return obj_patch

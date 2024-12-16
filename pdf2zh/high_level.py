"""Functions that can be used for the most common use-cases for pdf2zh.six"""

from typing import BinaryIO
import numpy as np
import tqdm
import sys
from pymupdf import Font, Document
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfexceptions import PDFValueError
from pdf2zh.converter import TranslateConverter
from pdf2zh.pdfinterp import PDFPageInterpreterEx
from pdf2zh.doclayout import DocLayoutModel
from pathlib import Path
from typing import Any, List, Optional
import urllib.request
import requests
import tempfile
import os
import io

model = DocLayoutModel.load_available()

resfont_map = {
    "zh-cn": "china-ss",
    "zh-tw": "china-ts",
    "zh-hans": "china-ss",
    "zh-hant": "china-ts",
    "zh": "china-ss",
    "ja": "japan-s",
    "ko": "korea-s",
}

noto_list = [
    "am",  # Amharic
    "ar",  # Arabic
    "bn",  # Bengali
    "bg",  # Bulgarian
    "chr",  # Cherokee
    "el",  # Greek
    "gu",  # Gujarati
    "iw",  # Hebrew
    "hi",  # Hindi
    # "ja",  # Japanese
    "kn",  # Kannada
    # "ko",  # Korean
    "ml",  # Malayalam
    "mr",  # Marathi
    "ru",  # Russian
    "sr",  # Serbian
    # "zh-cn",# SC
    "ta",  # Tamil
    "te",  # Telugu
    "th",  # Thai
    # "zh-tw",# TC
    "ur",  # Urdu
    "uk",  # Ukrainian
]


def check_files(files: List[str]) -> List[str]:
    files = [
        f for f in files if not f.startswith("http://")
    ]  # exclude online files, http
    files = [
        f for f in files if not f.startswith("https://")
    ]  # exclude online files, https
    missing_files = [file for file in files if not os.path.exists(file)]
    return missing_files


def translate_patch(
    inf: BinaryIO,
    pages: Optional[list[int]] = None,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_zh: Document = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    resfont: str = "",
    noto: Font = None,
    callback: object = None,
    **kwarg: Any,
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
        total_pages = doc_zh.page_count

    parser = PDFParser(inf)
    doc = PDFDocument(parser)
    with tqdm.tqdm(total=total_pages) as progress:
        for pageno, page in enumerate(PDFPage.create_pages(doc)):
            if pages and (pageno not in pages):
                continue
            progress.update()
            if callback:
                callback(progress)
            page.pageno = pageno
            pix = doc_zh[page.pageno].get_pixmap()
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
            page.page_xref = doc_zh.get_new_xref()  # hack 插入页面的新 xref
            doc_zh.update_object(page.page_xref, "<<>>")
            doc_zh.update_stream(page.page_xref, b"")
            doc_zh[page.pageno].set_contents(page.page_xref)
            interpreter.process_page(page)

    device.close()
    return obj_patch


def translate_stream(
    stream: bytes,
    pages: Optional[list[int]] = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    **kwarg: Any,
):
    font_list = [("tiro", None)]
    noto = None
    if lang_out.lower() in resfont_map:  # CJK
        resfont = resfont_map[lang_out.lower()]
        font_list.append((resfont, None))
    elif lang_out.lower() in noto_list:  # noto
        resfont = "noto"
        ttf_path = os.path.join(tempfile.gettempdir(), "GoNotoKurrent-Regular.ttf")
        if not os.path.exists(ttf_path):
            print("Downloading Noto font...")
            urllib.request.urlretrieve(
                "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf",
                ttf_path,
            )
        font_list.append(("noto", ttf_path))
        noto = Font("noto", ttf_path)
    else:  # fallback
        resfont = "china-ss"
        font_list.append(("china-ss", None))

    doc_en = Document(stream=stream)
    doc_zh = Document(stream=stream)
    page_count = doc_zh.page_count
    # font_list = [("china-ss", None), ("tiro", None)]
    font_id = {}
    for page in doc_zh:
        for font in font_list:
            font_id[font[0]] = page.insert_font(font[0], font[1])
    xreflen = doc_zh.xref_length()
    for xref in range(1, xreflen):
        for label in ["Resources/", ""]:  # 可能是基于 xobj 的 res
            try:  # xref 读写可能出错
                font_res = doc_zh.xref_get_key(xref, f"{label}Font")
                if font_res[0] == "dict":
                    for font in font_list:
                        font_exist = doc_zh.xref_get_key(xref, f"{label}Font/{font[0]}")
                        if font_exist[0] == "null":
                            doc_zh.xref_set_key(
                                xref,
                                f"{label}Font/{font[0]}",
                                f"{font_id[font[0]]} 0 R",
                            )
            except Exception:
                pass

    fp = io.BytesIO()
    doc_zh.save(fp)
    obj_patch: dict = translate_patch(fp, **locals())

    for obj_id, ops_new in obj_patch.items():
        # ops_old=doc_en.xref_stream(obj_id)
        # print(obj_id)
        # print(ops_old)
        # print(ops_new.encode())
        doc_zh.update_stream(obj_id, ops_new.encode())

    doc_en.insert_file(doc_zh)
    for id in range(page_count):
        doc_en.move_page(page_count + id, id * 2 + 1)

    return doc_zh.write(deflate=1), doc_en.write(deflate=1)


def translate(
    files: list[str],
    output: str = "",
    pages: Optional[list[int]] = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    **kwarg: Any,
):
    if not files:
        raise PDFValueError("No files to process.")

    missing_files = check_files(files)

    if missing_files:
        print("The following files do not exist:", file=sys.stderr)
        for file in missing_files:
            print(f"  {file}", file=sys.stderr)
        raise PDFValueError("Some files do not exist.")

    result_files = []

    for file in files:
        if file is str and (file.startswith("http://") or file.startswith("https://")):
            print("Online files detected, downloading...")
            try:
                r = requests.get(file, allow_redirects=True)
                if r.status_code == 200:
                    if not os.path.exists("./pdf2zh_files"):
                        print("Making a temporary dir for downloading PDF files...")
                        os.mkdir(os.path.dirname("./pdf2zh_files"))
                    with open("./pdf2zh_files/tmp_download.pdf", "wb") as f:
                        print(f"Writing the file: {file}...")
                        f.write(r.content)
                    file = "./pdf2zh_files/tmp_download.pdf"
                else:
                    r.raise_for_status()
            except Exception as e:
                raise PDFValueError(
                    f"Errors occur in downloading the PDF file. Please check the link(s).\nError:\n{e}"
                )
        filename = os.path.splitext(os.path.basename(file))[0]

        doc_raw = open(file, "rb")
        s_raw = doc_raw.read()
        s_mono, s_dual = translate_stream(s_raw, **locals())
        file_mono = Path(output) / f"{filename}-mono.pdf"
        file_dual = Path(output) / f"{filename}-dual.pdf"
        doc_mono = open(file_mono, "wb")
        doc_dual = open(file_dual, "wb")
        doc_mono.write(s_mono)
        doc_dual.write(s_dual)
        result_files.append((str(file_mono), str(file_dual)))

    return result_files

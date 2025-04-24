"""Functions that can be used for the most common use-cases for pdf2zh.six"""

import asyncio
import io
import logging
import os
import re
import sys
import tempfile
from asyncio import CancelledError
from pathlib import Path
from string import Template
from typing import Any, BinaryIO, Dict, List, Optional

import numpy as np
import requests
import tqdm
from babeldoc.assets.assets import get_font_and_metadata
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfexceptions import PDFValueError
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pymupdf import Document, Font

from pdf2zh.config import ConfigManager
from pdf2zh.converter import TranslateConverter
from pdf2zh.doclayout import OnnxModel
from pdf2zh.pdfinterp import PDFPageInterpreterEx

NOTO_NAME = "noto"

logger = logging.getLogger(__name__)

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
    "kn",  # Kannada
    "ml",  # Malayalam
    "mr",  # Marathi
    "ru",  # Russian
    "sr",  # Serbian
    "ta",  # Tamil
    "te",  # Telugu
    "th",  # Thai
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
    noto_name: str = "",
    noto: Font = None,
    callback: object = None,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    ignore_cache: bool = False,
    progress_bar: tqdm.tqdm = None,
    **kwarg: Any,
) -> None:
    rsrcmgr = PDFResourceManager()
    layout = {}
    device = TranslateConverter(
        rsrcmgr,
        vfont,
        vchar,
        thread,
        layout,
        lang_in,
        lang_out,
        service,
        noto_name,
        noto,
        envs,
        prompt,
        ignore_cache,
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

    should_close_pbar = False
    if progress_bar is None:
        progress_bar = tqdm.tqdm(total=total_pages)
        should_close_pbar = True

    try:
        for pageno, page in enumerate(PDFPage.create_pages(doc)):
            if cancellation_event and cancellation_event.is_set():
                raise CancelledError("task cancelled")
            if pages and (pageno not in pages):
                continue
            progress_bar.update(1)
            if callback:
                callback(progress_bar)
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
                if page_layout.names[int(d.cls)] not in vcls:
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
    finally:
        if should_close_pbar:
            progress_bar.close()

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
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    ignore_cache: bool = False,
    chunk_size: int = 20,  # Process this many pages at a time
    **kwarg: Any,
):
    font_list = [("tiro", None)]

    font_path = download_remote_fonts(lang_out.lower())
    noto_name = NOTO_NAME
    noto = Font(noto_name, font_path)
    font_list.append((noto_name, font_path))

    # Open the original document
    doc_en = Document(stream=stream)
    page_count = doc_en.page_count

    # Create temporary stream for working copy
    temp_stream = io.BytesIO()
    doc_en.save(temp_stream)

    # Create output documents
    doc_zh_final = Document()
    doc_en_final = Document()

    # Process document in chunks to reduce memory usage
    if pages:
        # When specific pages are requested
        page_chunks = [
            pages[i : i + chunk_size] for i in range(0, len(pages), chunk_size)
        ]
        total_pages = len(pages)
    else:
        # When processing all pages
        all_pages = list(range(page_count))
        page_chunks = [
            all_pages[i : i + chunk_size] for i in range(0, len(all_pages), chunk_size)
        ]
        total_pages = page_count

    # Create a single progress bar for the entire process
    with tqdm.tqdm(total=total_pages, desc="Translating PDF") as progress_bar:
        for chunk_idx, chunk_pages in enumerate(page_chunks):
            if cancellation_event and cancellation_event.is_set():
                raise CancelledError("task cancelled")

            # Reset the stream position and create a new document for this chunk
            temp_stream.seek(0)
            doc_zh = Document(stream=temp_stream)

            # Set up fonts for this document chunk
            font_id = {}
            for page in doc_zh:
                for font in font_list:
                    font_id[font[0]] = page.insert_font(font[0], font[1])

            # Apply fonts to resources
            xreflen = doc_zh.xref_length()
            for xref in range(1, xreflen):
                for label in ["Resources/", ""]:  # 可能是基于 xobj 的 res
                    try:  # xref 读写可能出错
                        font_res = doc_zh.xref_get_key(xref, f"{label}Font")
                        target_key_prefix = f"{label}Font/"
                        if font_res[0] == "xref":
                            resource_xref_id = re.search(
                                "(\\d+) 0 R", font_res[1]
                            ).group(1)
                            xref = int(resource_xref_id)
                            font_res = ("dict", doc_zh.xref_object(xref))
                            target_key_prefix = ""

                        if font_res[0] == "dict":
                            for font in font_list:
                                target_key = f"{target_key_prefix}{font[0]}"
                                font_exist = doc_zh.xref_get_key(xref, target_key)
                                if font_exist[0] == "null":
                                    doc_zh.xref_set_key(
                                        xref,
                                        target_key,
                                        f"{font_id[font[0]]} 0 R",
                                    )
                    except Exception:
                        pass

            # Create buffer for processing
            fp = io.BytesIO()
            doc_zh.save(fp)

            # Only process the current chunk of pages
            chunk_local_pages = [
                p % page_count for p in chunk_pages
            ]  # Normalize page numbers
            obj_patch: dict = translate_patch(
                fp,
                pages=chunk_local_pages,
                doc_zh=doc_zh,
                lang_in=lang_in,
                lang_out=lang_out,
                service=service,
                thread=thread,
                vfont=vfont,
                vchar=vchar,
                noto_name=noto_name,
                noto=noto,
                callback=callback,
                cancellation_event=cancellation_event,
                model=model,
                envs=envs,
                prompt=prompt,
                ignore_cache=ignore_cache,
                progress_bar=progress_bar,
                **kwarg,
            )

            # Apply patches to the current chunk
            for obj_id, ops_new in obj_patch.items():
                doc_zh.update_stream(obj_id, ops_new.encode())

            # Subset fonts for the current chunk if requested
            if not skip_subset_fonts:
                doc_zh.subset_fonts(fallback=True)

            # Extract processed pages from doc_zh and add to final document
            for page_idx in chunk_pages:
                if 0 <= page_idx < page_count:
                    # Add original page to final document
                    doc_en_final.insert_pdf(
                        doc_en, from_page=page_idx, to_page=page_idx
                    )

                    # Add translated page to final document
                    doc_zh_final.insert_pdf(
                        doc_zh, from_page=page_idx, to_page=page_idx
                    )

            # Free memory for this chunk
            doc_zh = None

    # Merge translated pages into the dual-language document
    doc_dual = Document()

    # First add all original pages
    doc_dual.insert_pdf(doc_en_final)

    # Then insert translated pages between original pages
    for i in range(doc_en_final.page_count):
        # Insert translated page after each original page
        doc_dual.insert_pdf(doc_zh_final, from_page=i, to_page=i)
        # Move the translated page to position after original page
        doc_dual.move_page(doc_dual.page_count - 1, 2 * i + 1)

    # Final subset of fonts if needed
    if not skip_subset_fonts:
        doc_zh_final.subset_fonts(fallback=True)
        doc_dual.subset_fonts(fallback=True)

    # Return both mono and dual documents
    return (
        doc_zh_final.write(deflate=True, garbage=3, use_objstms=1),
        doc_dual.write(deflate=True, garbage=3, use_objstms=1),
    )


def convert_to_pdfa(input_path, output_path):
    """
    Convert PDF to PDF/A format

    Args:
        input_path: Path to source PDF file
        output_path: Path to save PDF/A file
    """
    from pikepdf import Dictionary, Name, Pdf

    # Open the PDF file
    pdf = Pdf.open(input_path)

    # Add PDF/A conformance metadata
    metadata = {
        "pdfa_part": "2",
        "pdfa_conformance": "B",
        "title": pdf.docinfo.get("/Title", ""),
        "author": pdf.docinfo.get("/Author", ""),
        "creator": "PDF Math Translate",
    }

    with pdf.open_metadata() as meta:
        meta.load_from_docinfo(pdf.docinfo)
        meta["pdfaid:part"] = metadata["pdfa_part"]
        meta["pdfaid:conformance"] = metadata["pdfa_conformance"]

    # Create OutputIntent dictionary
    output_intent = Dictionary(
        {
            "/Type": Name("/OutputIntent"),
            "/S": Name("/GTS_PDFA1"),
            "/OutputConditionIdentifier": "sRGB IEC61966-2.1",
            "/RegistryName": "http://www.color.org",
            "/Info": "sRGB IEC61966-2.1",
        }
    )

    # Add output intent to PDF root
    if "/OutputIntents" not in pdf.Root:
        pdf.Root.OutputIntents = [output_intent]
    else:
        pdf.Root.OutputIntents.append(output_intent)

    # Save as PDF/A
    pdf.save(output_path, linearize=True)
    pdf.close()


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
    compatible: bool = False,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    ignore_cache: bool = False,
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
        if type(file) is str and (
            file.startswith("http://") or file.startswith("https://")
        ):
            print("Online files detected, downloading...")
            try:
                r = requests.get(file, allow_redirects=True)
                if r.status_code == 200:
                    with tempfile.NamedTemporaryFile(
                        suffix=".pdf", delete=False
                    ) as tmp_file:
                        print(f"Writing the file: {file}...")
                        tmp_file.write(r.content)
                        file = tmp_file.name
                else:
                    r.raise_for_status()
            except Exception as e:
                raise PDFValueError(
                    f"Errors occur in downloading the PDF file. Please check the link(s).\nError:\n{e}"
                )
        filename = os.path.splitext(os.path.basename(file))[0]

        # If the commandline has specified converting to PDF/A format
        # --compatible / -cp
        if compatible:
            with tempfile.NamedTemporaryFile(
                suffix="-pdfa.pdf", delete=False
            ) as tmp_pdfa:
                print(f"Converting {file} to PDF/A format...")
                convert_to_pdfa(file, tmp_pdfa.name)
                doc_raw = open(tmp_pdfa.name, "rb")
                os.unlink(tmp_pdfa.name)
        else:
            doc_raw = open(file, "rb")
        s_raw = doc_raw.read()
        doc_raw.close()

        temp_dir = Path(tempfile.gettempdir())
        file_path = Path(file)
        try:
            if file_path.exists() and file_path.resolve().is_relative_to(
                temp_dir.resolve()
            ):
                file_path.unlink(missing_ok=True)
                logger.debug(f"Cleaned temp file: {file_path}")
        except Exception:
            logger.warning(f"Failed to clean temp file {file_path}", exc_info=True)

        s_mono, s_dual = translate_stream(
            s_raw,
            **locals(),
        )
        file_mono = Path(output) / f"{filename}-mono.pdf"
        file_dual = Path(output) / f"{filename}-dual.pdf"
        doc_mono = open(file_mono, "wb")
        doc_dual = open(file_dual, "wb")
        doc_mono.write(s_mono)
        doc_dual.write(s_dual)
        doc_mono.close()
        doc_dual.close()
        result_files.append((str(file_mono), str(file_dual)))

    return result_files


def download_remote_fonts(lang: str):
    lang = lang.lower()
    LANG_NAME_MAP = {
        **{la: "GoNotoKurrent-Regular.ttf" for la in noto_list},
        **{
            la: f"SourceHanSerif{region}-Regular.ttf"
            for region, langs in {
                "CN": ["zh-cn", "zh-hans", "zh"],
                "TW": ["zh-tw", "zh-hant"],
                "JP": ["ja"],
                "KR": ["ko"],
            }.items()
            for la in langs
        },
    }
    font_name = LANG_NAME_MAP.get(lang, "GoNotoKurrent-Regular.ttf")

    # docker
    font_path = ConfigManager.get("NOTO_FONT_PATH", Path("/app", font_name).as_posix())
    if not Path(font_path).exists():
        font_path, _ = get_font_and_metadata(font_name)
        font_path = font_path.as_posix()

    logger.info(f"use font: {font_path}")

    return font_path

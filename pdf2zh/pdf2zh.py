#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import argparse
import os
import sys
import logging
from pathlib import Path
from typing import Any, Container, Iterable, List, Optional
import urllib.request
from pdfminer.pdfexceptions import PDFValueError

import pymupdf
import requests
import tempfile

from pdf2zh import __version__, log
from pdf2zh.high_level import extract_text_to_fp
from pdf2zh.doclayout import DocLayoutModel

logging.basicConfig()

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


def extract_text(
    files: Iterable[str] = [],
    pages: Optional[Container[int]] = None,
    password: str = "",
    debug: bool = False,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    callback: object = None,
    output: str = "",
    **kwargs: Any,
):
    if debug:
        log.setLevel(logging.DEBUG)

    if not files:
        raise PDFValueError("Must provide files to work upon!")

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
            noto = pymupdf.Font("noto", ttf_path)
        else:  # fallback
            resfont = "china-ss"
            font_list.append(("china-ss", None))

        doc_en = pymupdf.open(file)
        page_count = doc_en.page_count
        # font_list = [("china-ss", None), ("tiro", None)]
        font_id = {}
        for page in doc_en:
            for font in font_list:
                font_id[font[0]] = page.insert_font(font[0], font[1])
        xreflen = doc_en.xref_length()
        for xref in range(1, xreflen):
            for label in ["Resources/", ""]:  # 可能是基于 xobj 的 res
                try:  # xref 读写可能出错
                    font_res = doc_en.xref_get_key(xref, f"{label}Font")
                    if font_res[0] == "dict":
                        for font in font_list:
                            font_exist = doc_en.xref_get_key(
                                xref, f"{label}Font/{font[0]}"
                            )
                            if font_exist[0] == "null":
                                doc_en.xref_set_key(
                                    xref,
                                    f"{label}Font/{font[0]}",
                                    f"{font_id[font[0]]} 0 R",
                                )
                except Exception:
                    pass
        doc_en.save(Path(output) / f"{filename}-en.pdf")

        with open(Path(output) / f"{filename}-en.pdf", "rb") as fp:
            obj_patch: dict = extract_text_to_fp(fp, model=model, **locals())

        for obj_id, ops_new in obj_patch.items():
            # ops_old=doc_en.xref_stream(obj_id)
            # print(obj_id)
            # print(ops_old)
            # print(ops_new.encode())
            doc_en.update_stream(obj_id, ops_new.encode())

        doc_zh = doc_en
        doc_dual = pymupdf.open(Path(output) / f"{filename}-en.pdf")
        doc_dual.insert_file(doc_zh)
        for id in range(page_count):
            doc_dual.move_page(page_count + id, id * 2 + 1)
        doc_zh.save(Path(output) / f"{filename}-zh.pdf", deflate=1)
        doc_dual.save(Path(output) / f"{filename}-dual.pdf", deflate=1)
        doc_zh.close()
        doc_dual.close()
        os.remove(Path(output) / f"{filename}-en.pdf")

    return


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument(
        "files",
        type=str,
        default=None,
        nargs="*",
        help="One or more paths to PDF files.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"pdf2zh v{__version__}",
    )
    parser.add_argument(
        "--debug",
        "-d",
        default=False,
        action="store_true",
        help="Use debug logging level.",
    )
    parse_params = parser.add_argument_group(
        "Parser",
        description="Used during PDF parsing",
    )
    parse_params.add_argument(
        "--pages",
        "-p",
        type=str,
        help="The list of page numbers to parse.",
    )
    parse_params.add_argument(
        "--password",
        "-P",
        type=str,
        default="",
        help="The password to use for decrypting PDF file.",
    )
    parse_params.add_argument(
        "--vfont",
        "-f",
        type=str,
        default="",
        help="The regex to math font name of formula.",
    )
    parse_params.add_argument(
        "--vchar",
        "-c",
        type=str,
        default="",
        help="The regex to math character of formula.",
    )
    parse_params.add_argument(
        "--lang-in",
        "-li",
        type=str,
        default="en",
        help="The code of source language.",
    )
    parse_params.add_argument(
        "--lang-out",
        "-lo",
        type=str,
        default="zh",
        help="The code of target language.",
    )
    parse_params.add_argument(
        "--service",
        "-s",
        type=str,
        default="google",
        help="The service to use for translation.",
    )
    parse_params.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Output directory for files.",
    )
    parse_params.add_argument(
        "--thread",
        "-t",
        type=int,
        default=4,
        help="The number of threads to execute translation.",
    )
    parse_params.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interact with GUI.",
    )
    parse_params.add_argument(
        "--share",
        action="store_true",
        help="Enable Gradio Share",
    )

    return parser


def parse_args(args: Optional[List[str]]) -> argparse.Namespace:
    parsed_args = create_parser().parse_args(args=args)

    if parsed_args.pages:
        pages = []
        for p in parsed_args.pages.split(","):
            if "-" in p:
                start, end = p.split("-")
                pages.extend(range(int(start) - 1, int(end)))
            else:
                pages.append(int(p) - 1)
        parsed_args.pages = pages

    return parsed_args


def main(args: Optional[List[str]] = None) -> int:
    parsed_args = parse_args(args)

    missing_files = check_files(parsed_args.files)
    if missing_files:
        print("The following files do not exist:", file=sys.stderr)
        for file in missing_files:
            print(f"  {file}", file=sys.stderr)
        return -1
    if parsed_args.interactive:
        from pdf2zh.gui import setup_gui

        setup_gui(parsed_args.share)
        return 0

    extract_text(**vars(parsed_args))
    return 0


if __name__ == "__main__":
    sys.exit(main())

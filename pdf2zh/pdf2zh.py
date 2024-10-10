#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

import argparse
import logging
import os
import sys
from typing import Any, Container, Iterable, List, Optional
import pymupdf
import layoutparser as lp
import tempfile
import urllib.request

import pdf2zh.high_level
from pdf2zh.layout import LAParams
from pdf2zh.pdfexceptions import PDFValueError
from pdf2zh.utils import AnyIO

logging.basicConfig()

OUTPUT_TYPES = ((".htm", "html"), (".html", "html"), (".xml", "xml"), (".tag", "tag"))


def float_or_disabled(x: str) -> Optional[float]:
    if x.lower().strip() == "disabled":
        return None
    try:
        return float(x)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {x}")


def extract_text(
    files: Iterable[str] = [],
    outfile: str = "-",
    laparams: Optional[LAParams] = None,
    output_type: str = "text",
    codec: str = "utf-8",
    strip_control: bool = False,
    maxpages: int = 0,
    pages: Optional[Container[int]] = None,
    password: str = "",
    scale: float = 1.0,
    rotation: int = 0,
    layoutmode: str = "normal",
    output_dir: Optional[str] = None,
    debug: bool = False,
    disable_caching: bool = False,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    lang_in: str = "",
    lang_out: str = "",
    **kwargs: Any,
) -> AnyIO:
    if not files:
        raise PDFValueError("Must provide files to work upon!")

    if output_type == "text" and outfile != "-":
        for override, alttype in OUTPUT_TYPES:
            if outfile.endswith(override):
                output_type = alttype

    outfp: AnyIO = sys.stdout
    pth = os.path.join(tempfile.gettempdir(), 'mfd-tf_efficientdet_d0.pth.tar')
    if not os.path.exists(pth):
        print('Downloading...')
        urllib.request.urlretrieve("https://www.dropbox.com/s/dkr22iux7thlhel/mfd-tf_efficientdet_d0.pth.tar?dl=1",pth)
    model = lp.EfficientDetLayoutModel("lp://efficientdet/MFD/tf_efficientdet_d0",pth)

    for file in files:

        filename = os.path.splitext(os.path.basename(file))[0]

        doc_en = pymupdf.open(file)
        page_count=doc_en.page_count
        for page in doc_en:
            page.insert_font('china-ss')
            page.insert_font('tiro')
        doc_en.save('output-en.pdf')

        with open('output-en.pdf', "rb") as fp:
            pdf2zh.high_level.extract_text_to_fp(fp, **locals())

        doc_en.close()
        doc_zh = pymupdf.open('output-zh.pdf')
        doc_dual = pymupdf.open('output-en.pdf')
        doc_dual.insert_file(doc_zh)
        for id in range(page_count):
            doc_dual.move_page(page_count+id,id*2+1)
        doc_zh.save(f'{filename}-zh.pdf',deflate=1)
        doc_dual.save(f'{filename}-dual.pdf',deflate=1)
        doc_zh.close()
        doc_dual.close()

        os.remove('output-en.pdf')
        os.remove('output-zh.pdf')

    return


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument(
        "files",
        type=str,
        default=None,
        nargs="+",
        help="One or more paths to PDF files.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"pdf2zh v{pdf2zh.__version__}",
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
        default="zh-CN",
        help="The code of target language.",
    )
    parse_params.add_argument(
        "--thread",
        "-t",
        type=int,
        default=4,
        help="The number of threads to execute translation.",
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
    extract_text(**vars(parsed_args))
    return 0


if __name__ == "__main__":
    sys.exit(main())

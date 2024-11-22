#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import TYPE_CHECKING, Any, Container, Iterable, List, Optional

import pymupdf
from huggingface_hub import hf_hub_download

from pdf2zh import __version__
from pdf2zh.pdfexceptions import PDFValueError

if TYPE_CHECKING:
    from pdf2zh.layout import LAParams
    from pdf2zh.utils import AnyIO

OUTPUT_TYPES = ((".htm", "html"), (".html", "html"), (".xml", "xml"), (".tag", "tag"))


def setup_log() -> None:
    import doclayout_yolo

    logging.basicConfig()
    doclayout_yolo.utils.LOGGER.setLevel(logging.WARNING)


def check_files(files: List[str]) -> List[str]:
    missing_files = [file for file in files if not os.path.exists(file)]
    return missing_files


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
    service: str = "",
    **kwargs: Any,
) -> AnyIO:
    import doclayout_yolo

    import pdf2zh.high_level

    if not files:
        raise PDFValueError("Must provide files to work upon!")

    if output_type == "text" and outfile != "-":
        for override, alttype in OUTPUT_TYPES:
            if outfile.endswith(override):
                output_type = alttype

    outfp: AnyIO = sys.stdout
    # pth = os.path.join(tempfile.gettempdir(), 'doclayout_yolo_docstructbench_imgsz1024.pt')
    # if not os.path.exists(pth):
    #     print('Downloading...')
    #     urllib.request.urlretrieve("http://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench/resolve/main/doclayout_yolo_docstructbench_imgsz1024.pt",pth)
    pth = hf_hub_download(
        repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
        filename="doclayout_yolo_docstructbench_imgsz1024.pt",
    )
    model = doclayout_yolo.YOLOv10(pth)

    for file in files:
        filename = os.path.splitext(os.path.basename(file))[0]

        doc_en = pymupdf.open(file)
        page_count = doc_en.page_count
        font_list = ["china-ss", "tiro"]
        font_id = {}
        for page in doc_en:
            for font in font_list:
                font_id[font] = page.insert_font(font)
        xreflen = doc_en.xref_length()
        for xref in range(1, xreflen):
            for label in ["Resources/", ""]:  # 可能是基于 xobj 的 res
                try:  # xref 读写可能出错
                    font_res = doc_en.xref_get_key(xref, f"{label}Font")
                    if font_res[0] == "dict":
                        for font in font_list:
                            font_exist = doc_en.xref_get_key(
                                xref, f"{label}Font/{font}"
                            )
                            if font_exist[0] == "null":
                                doc_en.xref_set_key(
                                    xref, f"{label}Font/{font}", f"{font_id[font]} 0 R"
                                )
                except:
                    pass
        doc_en.save(f"{filename}-en.pdf")

        with open(f"{filename}-en.pdf", "rb") as fp:
            obj_patch: dict = pdf2zh.high_level.extract_text_to_fp(fp, **locals())

        for obj_id, ops_new in obj_patch.items():
            # ops_old=doc_en.xref_stream(obj_id)
            # print(obj_id)
            # print(ops_old)
            # print(ops_new.encode())
            doc_en.update_stream(obj_id, ops_new.encode())

        doc_zh = doc_en
        doc_dual = pymupdf.open(f"{filename}-en.pdf")
        doc_dual.insert_file(doc_zh)
        for id in range(page_count):
            doc_dual.move_page(page_count + id, id * 2 + 1)
        doc_zh.save(f"{filename}-zh.pdf", deflate=1)
        doc_dual.save(f"{filename}-dual.pdf", deflate=1)
        doc_zh.close()
        doc_dual.close()
        try:  # fix (main): permission error @ https://github.com/Byaidu/PDFMathTranslate/issues/84
            os.remove(f"{filename}-en.pdf")
        except Exception as e:
            print(f"File removal failed due to occupation / not existing, pass.\n{e}")
            pass

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
        default="auto",
        help="The code of source language.",
    )
    parse_params.add_argument(
        "--lang-out",
        "-lo",
        type=str,
        default="auto",
        help="The code of target language.",
    )
    parse_params.add_argument(
        "--service",
        "-s",
        type=str,
        default="google",
        help="The service to use for translating.",
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
    parser.add_argument(
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

        if parsed_args.share:
            setup_gui(True)
            return 0
        else:
            setup_gui()
            return 0

    setup_log()
    extract_text(**vars(parsed_args))
    return 0


if __name__ == "__main__":
    sys.exit(main())

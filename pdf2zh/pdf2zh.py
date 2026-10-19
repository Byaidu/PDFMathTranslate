#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from string import Template
from typing import List, Optional

from pdf2zh import __version__, log

logger = logging.getLogger(__name__)

KERNEL_ALIASES = {"fast": "legacy", "precise": "babeldoc"}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument(
        "files",
        type=str,
        default=None,
        nargs="*",
        help="One or more paths to PDF/Word files.",
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
        default=None,
        help="Translation workers: default 4, or 16 with --ultrafast.",
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
    parse_params.add_argument(
        "--flask",
        action="store_true",
        help="flask",
    )
    parse_params.add_argument(
        "--celery",
        action="store_true",
        help="celery",
    )
    parse_params.add_argument(
        "--authorized",
        type=str,
        nargs="+",
        help="user name and password.",
    )
    parse_params.add_argument(
        "--prompt",
        type=str,
        help="user custom prompt.",
    )

    parse_params.add_argument(
        "--compatible",
        "-cp",
        action="store_true",
        help="Convert the PDF file into PDF/A format to improve compatibility.",
    )

    parse_params.add_argument(
        "--ultrafast",
        action="store_true",
        help="Use pdf-inspector text layout without neural layout models or OCR.",
    )

    parse_params.add_argument(
        "--onnx",
        type=str,
        help="custom onnx model path.",
    )

    parse_params.add_argument(
        "--backend",
        type=str,
        choices=["auto", "cpu", "cuda", "dml"],
        default="auto",
        help="ONNX Runtime execution provider: auto, cpu, cuda, dml.",
    )

    parse_params.add_argument(
        "--serverport",
        type=int,
        help="custom WebUI port.",
    )

    parse_params.add_argument(
        "--dir",
        action="store_true",
        help="translate directory.",
    )

    parse_params.add_argument(
        "--config",
        type=str,
        help="config file.",
    )

    parse_params.add_argument(
        "--kernel",
        "-k",
        type=str,
        choices=["auto", "babeldoc", "legacy"],
        default=None,
        help="Translation kernel: babeldoc (default when installed) or legacy "
        "(pdf2zh v1, needs pdf2zh[legacy]). auto picks babeldoc first.",
    )

    parse_params.add_argument(
        "--mode",
        type=str,
        choices=["fast", "precise"],
        default=None,
        help="Deprecated alias of --kernel: fast = legacy, precise = babeldoc.",
    )

    parse_params.add_argument(
        "--babeldoc",
        default=False,
        action="store_true",
        help="Deprecated alias of --kernel babeldoc.",
    )

    parse_params.add_argument(
        "--skip-subset-fonts",
        action="store_true",
        help="Skip font subsetting. "
        "This option can improve compatibility "
        "but will increase the size of the output file.",
    )

    parse_params.add_argument(
        "--ignore-cache",
        action="store_true",
        help="Ignore cache and force retranslation.",
    )

    parse_params.add_argument(
        "--mcp", action="store_true", help="Launch pdf2zh MCP server in STDIO mode"
    )

    parse_params.add_argument(
        "--sse", action="store_true", help="Launch pdf2zh MCP server in SSE mode"
    )

    parse_params.add_argument(
        "--json",
        action="store_true",
        help="Print the result as one JSON object on stdout, for programs that "
        "run pdf2zh as a subprocess. Logs stay on stderr.",
    )

    return parser


def parse_args(args: Optional[List[str]]) -> argparse.Namespace:
    parser = create_parser()
    parsed_args = parser.parse_args(args=args)
    if parsed_args.thread is None:
        parsed_args.thread = 16 if parsed_args.ultrafast else 4
    if parsed_args.thread < 1:
        parser.error("--thread must be at least 1")
    requested = {
        k
        for k in (
            parsed_args.kernel,
            KERNEL_ALIASES.get(parsed_args.mode),
            "babeldoc" if parsed_args.babeldoc else None,
        )
        if k and k != "auto"
    }
    if len(requested) > 1:
        parser.error("--kernel, --mode and --babeldoc select different kernels")
    legacy_only = parsed_args.ultrafast or parsed_args.onnx
    if requested:
        parsed_args.kernel = requested.pop()
    elif legacy_only:
        parsed_args.kernel = "legacy"
    else:
        parsed_args.kernel = "auto"
    if parsed_args.ultrafast and (
        parsed_args.kernel != "legacy"
        or parsed_args.onnx
        or parsed_args.interactive
        or parsed_args.flask
        or parsed_args.celery
        or parsed_args.mcp
        or parsed_args.sse
    ):
        parser.error(
            "--ultrafast requires the legacy kernel without --onnx or server options"
        )
    if parsed_args.onnx and parsed_args.kernel == "babeldoc":
        parser.error("--onnx requires the legacy kernel")

    if parsed_args.pages:
        pages = []
        for p in parsed_args.pages.split(","):
            if "-" in p:
                start, end = p.split("-")
                pages.extend(range(int(start) - 1, int(end)))
            else:
                pages.append(int(p) - 1)
        parsed_args.raw_pages = parsed_args.pages
        parsed_args.pages = pages

    return parsed_args


def find_all_files_in_directory(directory_path):
    """
    Recursively search all PDF files in the given directory and return their paths as a list.

    :param directory_path: str, the path to the directory to search
    :return: list of PDF file paths
    """
    # Check if the provided path is a directory
    if not os.path.isdir(directory_path):
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    file_paths = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory_path):
        for file in files:
            # Check if the file is a PDF
            if file.lower().endswith((".pdf", ".doc", ".docx")):
                # Append the full file path to the list
                file_paths.append(os.path.join(root, file))

    return file_paths


def main(args: Optional[List[str]] = None) -> int:
    parsed_args = parse_args(args)

    from rich.console import Console
    from rich.logging import RichHandler

    # Logs go to stderr: in MCP STDIO mode stdout carries the protocol.
    logging.basicConfig(
        level=logging.INFO, handlers=[RichHandler(console=Console(stderr=True))]
    )

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False

    if parsed_args.config:
        from pdf2zh.config import ConfigManager

        ConfigManager.custome_config(parsed_args.config)

    if parsed_args.debug:
        log.setLevel(logging.DEBUG)

    if parsed_args.interactive or parsed_args.flask or parsed_args.celery:
        # The web UI and the HTTP backend run on the legacy kernel.
        _require_extra(
            "gradio" if parsed_args.interactive else "flask",
            "gui" if parsed_args.interactive else "backend",
        )
        _load_layout_model(parsed_args)

    if parsed_args.interactive:
        from pdf2zh.gui import setup_gui

        if parsed_args.serverport:
            setup_gui(
                parsed_args.share, parsed_args.authorized, int(parsed_args.serverport)
            )
        else:
            setup_gui(parsed_args.share, parsed_args.authorized)
        return 0

    if parsed_args.flask:
        from pdf2zh.backend import flask_app

        flask_app.run(port=11008)
        return 0

    if parsed_args.celery:
        from pdf2zh.backend import celery_app

        celery_app.start(argv=sys.argv[2:])
        return 0

    if parsed_args.prompt:
        try:
            with open(parsed_args.prompt, "r", encoding="utf-8") as file:
                content = file.read()
            parsed_args.prompt = Template(content)
        except Exception:
            raise ValueError("prompt error.")

    if parsed_args.mcp:
        logging.getLogger("mcp").setLevel(logging.ERROR)
        from pdf2zh.mcp_server import create_mcp_app

        mcp = create_mcp_app()
        if parsed_args.sse:
            import uvicorn

            uvicorn.run(mcp.sse_app())
            return 0
        mcp.run()
        return 0

    from pdf2zh.kernel import KernelRegistry
    from pdf2zh.kernel.protocol import TranslateRequest

    try:
        KernelRegistry.switch(parsed_args.kernel)
    except RuntimeError as e:
        logger.error(str(e))
        if parsed_args.json:
            _print_json({"ok": False, "error": str(e)})
        return 1
    kernel = KernelRegistry.get()
    logger.info(f"Using kernel: {kernel.name} {kernel.version}")
    if kernel.name == "legacy":
        _load_layout_model(parsed_args)

    if parsed_args.dir:
        parsed_args.files = find_all_files_in_directory(parsed_args.files[0])

    # Extract prompt text (may be a Template object from file reading above)
    prompt_text = None
    if parsed_args.prompt:
        prompt_text = (
            parsed_args.prompt.template
            if hasattr(parsed_args.prompt, "template")
            else parsed_args.prompt
        )

    request = TranslateRequest(
        files=parsed_args.files,
        output=parsed_args.output,
        pages=parsed_args.pages,
        lang_in=parsed_args.lang_in,
        lang_out=parsed_args.lang_out,
        service=parsed_args.service,
        thread=parsed_args.thread,
        vfont=parsed_args.vfont,
        vchar=parsed_args.vchar,
        envs={},
        prompt=prompt_text,
        skip_subset_fonts=parsed_args.skip_subset_fonts,
        ignore_cache=parsed_args.ignore_cache,
        compatible=parsed_args.compatible,
        debug=parsed_args.debug,
        ultrafast=parsed_args.ultrafast,
    )
    if not parsed_args.json:
        kernel.translate(request)
        return 0

    # Keep stdout to the single JSON object: no progress bars, and anything
    # the kernels print goes to stderr.
    import contextlib

    try:
        with contextlib.redirect_stdout(sys.stderr):
            results = kernel.translate(request, callback=lambda *args: None)
    except Exception as e:
        logger.exception("Translation failed")
        _print_json({"ok": False, "kernel": kernel.name, "error": str(e)})
        return 1
    _print_json(
        {
            "ok": True,
            "kernel": kernel.name,
            "results": [
                {
                    "input": str(source),
                    "mono": str(Path(r.mono_pdf).resolve()) if r.mono_pdf else None,
                    "dual": str(Path(r.dual_pdf).resolve()) if r.dual_pdf else None,
                }
                for source, r in zip(request.files, results)
            ],
        }
    )
    return 0


def _print_json(payload: dict) -> None:
    import json

    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _require_extra(module: str, extra: str) -> None:
    import importlib.util

    if importlib.util.find_spec(module) is None:
        raise SystemExit(
            f"This mode needs an optional dependency. "
            f"Install it with: pip install 'pdf2zh[{extra}]'"
        )


def _load_layout_model(parsed_args) -> None:
    """Load the DocLayout-YOLO model used by the legacy kernel."""
    if parsed_args.ultrafast:
        return
    from pdf2zh.doclayout import ModelInstance, OnnxModel, set_backend

    set_backend(parsed_args.backend)
    if parsed_args.onnx:
        ModelInstance.value = OnnxModel(parsed_args.onnx)
    else:
        ModelInstance.value = OnnxModel.load_available()


if __name__ == "__main__":
    sys.exit(main())

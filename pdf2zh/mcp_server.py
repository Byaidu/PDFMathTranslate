try:  # mcp >= 2 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import Context, MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import Context, FastMCP
from pathlib import Path
from typing import Optional

import contextlib
import io
import os


def create_mcp_app() -> FastMCP:
    mcp = FastMCP("pdf2zh")

    @mcp.tool()
    async def translate_pdf(
        file: str,
        lang_in: str,
        lang_out: str,
        ctx: Context,
        service: str = "google",
        kernel: str = "auto",
        pages: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        """
        translate given pdf or word document. Argument `file` is absolute path
        of input pdf/doc/docx, `lang_in` and `lang_out` is translate from and
        to language, and should be like google translate lang_code. `lang_in`
        can be `auto` if you can't determine input language. `service` is the
        translation service such as `google`, `deepl` or `openai:gpt-4o-mini`.
        `kernel` is `auto`, `babeldoc` or `legacy`. `pages` is a 1-based page
        list such as "1,3-5". Output goes next to the input unless
        `output_dir` is given.
        """
        from pdf2zh.kernel import KernelRegistry
        from pdf2zh.kernel.protocol import TranslateRequest

        engine = KernelRegistry.get(kernel)
        if not engine.is_available():
            KernelRegistry.switch(engine.name)  # raises with an install hint
        request = TranslateRequest(
            files=[file],
            lang_in=lang_in,
            lang_out=lang_out,
            service=service,
            pages=_parse_pages(pages),
            output=output_dir or os.path.dirname(file),
        )
        # Positional: mcp 1.x names the second argument message, 2.x data.
        await ctx.log("info", f"start translate {file} with {engine.name}")
        # stdout carries the MCP protocol in STDIO mode; keep kernels off it.
        with contextlib.redirect_stdout(io.StringIO()):
            results = await engine.translate_async(request, callback=_ignore)
        await ctx.log("info", "translate complete")
        lines = ["------------", "    translate complete"]
        for result in results:
            if result.mono_pdf:
                lines.append(f"    mono pdf file: {Path(result.mono_pdf).absolute()}")
            if result.dual_pdf:
                lines.append(f"    dual pdf file: {Path(result.dual_pdf).absolute()}")
        return "\n".join(lines) + "\n"

    @mcp.tool()
    def list_kernels() -> str:
        """List translation kernels, their versions and whether they are installed."""
        from pdf2zh.kernel import KernelRegistry
        from pdf2zh.kernel.registry import INSTALL_HINTS

        lines = []
        for name in ("babeldoc", "legacy"):
            engine = KernelRegistry.get(name)
            if engine.is_available():
                lines.append(f"{name}: installed, version {engine.version}")
            else:
                lines.append(f"{name}: not installed ({INSTALL_HINTS[name]})")
        return "\n".join(lines)

    return mcp


def _ignore(*args, **kwargs) -> None:
    pass


def _parse_pages(pages: Optional[str]) -> Optional[list[int]]:
    """Convert a 1-based "1,3-5" spec to 0-based page indexes."""
    if not pages:
        return None
    result = []
    for part in pages.split(","):
        start, _, end = part.strip().partition("-")
        result.extend(range(int(start) - 1, int(end or start)))
    return result


if __name__ == "__main__":
    import argparse

    mcp = create_mcp_app()
    parser = argparse.ArgumentParser(description="Run MCP SSE-based PDF2ZH server")

    parser.add_argument(
        "--sse",
        default=False,
        action="store_true",
        help="Run the server with SSE transport or STDIO",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", required=False, help="Host to bind"
    )
    parser.add_argument(
        "--port", type=int, default=3001, required=False, help="Port to bind"
    )

    args = parser.parse_args()
    if args.sse and args.host and args.port:
        import uvicorn

        uvicorn.run(mcp.sse_app(), host=args.host, port=args.port)
    else:
        mcp.run()

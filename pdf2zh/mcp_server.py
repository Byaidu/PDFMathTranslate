try:  # mcp >= 2 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import Context, MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import Context, FastMCP
from pathlib import Path
from typing import Optional

import contextlib
import io
import os


def transport_security():
    """Only localhost may call over HTTP; PDF2ZH_ALLOWED_HOSTS adds host names
    (comma-separated, e.g. a tunnel's), and "*" turns the check off."""
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [
        h.strip()
        for h in os.environ.get("PDF2ZH_ALLOWED_HOSTS", "").split(",")
        if h.strip()
    ]
    if "*" in hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts += ["127.0.0.1:*", "localhost:*"]
    origins = [f"{scheme}://{h}" for h in hosts for scheme in ("http", "https")]
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


def _accepts(func, name: str) -> bool:
    import inspect

    return name in inspect.signature(func).parameters


def create_mcp_app(http: bool = False) -> FastMCP:
    # mcp 1.x takes HTTP settings in the constructor, 2.x in streamable_http_app.
    # Stateless HTTP: no tool needs a session, and clients holding a session ID
    # from before a server restart would otherwise get 404 on every call.
    kwargs = {}
    if http and _accepts(FastMCP.__init__, "transport_security"):
        kwargs["transport_security"] = transport_security()
    if http and _accepts(FastMCP.__init__, "stateless_http"):
        kwargs["stateless_http"] = True
    mcp = FastMCP("pdf2zh", **kwargs)

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
        from pdf2zh.kernel.protocol import TranslateRequest, parse_pages

        engine = KernelRegistry.get(kernel)
        if not engine.is_available():
            KernelRegistry.switch(engine.name)  # raises with an install hint
        request = TranslateRequest(
            files=[file],
            lang_in=lang_in,
            lang_out=lang_out,
            service=service,
            pages=parse_pages(pages),
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

    from pdf2zh.mcp_reader import register as register_reader

    register_reader(mcp)
    return mcp


def create_http_app(mcp: FastMCP):
    """Streamable HTTP app serving the MCP endpoint at /mcp.

    Browser-based hosts call it cross-origin, so CORS is allowed for the same
    origins the transport security accepts: localhost and PDF2ZH_ALLOWED_HOSTS.
    """
    import re

    from starlette.middleware.cors import CORSMiddleware

    kwargs = {}
    if _accepts(mcp.streamable_http_app, "transport_security"):
        kwargs["transport_security"] = transport_security()
    if _accepts(mcp.streamable_http_app, "stateless_http"):
        kwargs["stateless_http"] = True
    app = mcp.streamable_http_app(**kwargs)
    extra = [
        h.strip()
        for h in os.environ.get("PDF2ZH_ALLOWED_HOSTS", "").split(",")
        if h.strip()
    ]
    hosts = ["localhost", r"127\.0\.0\.1"] + [re.escape(h) for h in extra if h != "*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            ".*" if "*" in extra else rf"https?://({'|'.join(hosts)})(:\d+)?"
        ),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
    )
    return app


def _ignore(*args, **kwargs) -> None:
    pass


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

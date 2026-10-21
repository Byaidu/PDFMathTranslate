# ChatGPT

ChatGPT connects to MCP servers over HTTPS, so it uses the [example server](../server/)'s `/mcp` endpoint. ChatGPT runs in the cloud and cannot read files on your computer: its tool, `translate_pdf_url`, takes a link to a PDF and returns download links for the translated and bilingual PDFs.

## Set up

1. Start the example server and expose it with a tunnel (or deploy it behind your own HTTPS reverse proxy):

   ```bash
   pip install pdf2zh
   cloudflared tunnel --url http://127.0.0.1:7861        # prints https://<tunnel-host>
   PDF2ZH_PUBLIC_URL=https://<tunnel-host> \
   PDF2ZH_ALLOWED_HOSTS=<tunnel-host> \
   python examples/server/server.py
   ```

   `PDF2ZH_PUBLIC_URL` makes the returned download links reachable from outside. `PDF2ZH_ALLOWED_HOSTS` lets requests for the tunnel's host name through; the server rejects unknown hosts by default.

2. In ChatGPT, turn on developer mode for connectors and create a connector with the URL `https://<tunnel-host>/mcp` and no authentication. Menu names change between ChatGPT releases; see OpenAI's documentation on connecting MCP servers.

3. In a chat, enable the connector and ask, for example: *"Translate https://arxiv.org/pdf/2407.10934 into Chinese."*

## PDF reader

ChatGPT also shows `open_pdf_reader` from pdf2zh's own MCP server: the PDF appears in the chat and pages are translated as you scroll. Run it on your computer over HTTP and expose it with a tunnel; the reader then opens PDFs on your computer by path, as well as links:

```bash
pip install pdf2zh
cloudflared tunnel --url http://127.0.0.1:7862        # prints https://<tunnel-host>
PDF2ZH_ALLOWED_HOSTS=<tunnel-host> pdf2zh --mcp --http
```

Create a connector with the URL `https://<tunnel-host>/mcp`, then ask: *"Open /Users/me/Downloads/paper.pdf in the pdf2zh reader."*

This server can read any PDF on your computer and translate with your service keys, for anyone who has the tunnel address. Stop the tunnel when you are done.

## Before sharing it

The example server has no authentication, keeps jobs in memory and downloads any URL it is given. Anyone who can reach it can use your translation service quota. For more than a personal tunnel, add authentication (ChatGPT connectors support OAuth), restrict which URLs it fetches, and store files somewhere durable.

## Status

The `/mcp` endpoint and `translate_pdf_url` are tested with the MCP Python SDK's Streamable HTTP client. The ChatGPT connector steps have not been run against ChatGPT.

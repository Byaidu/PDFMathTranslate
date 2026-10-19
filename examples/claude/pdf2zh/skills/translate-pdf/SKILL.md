---
name: translate-pdf
description: Translate a PDF, DOC or DOCX file while keeping formulas, figures and layout. Use when the user asks to translate a paper or document file into another language.
---

Translate with the `translate_pdf` tool of the `pdf2zh` MCP server.

1. Resolve the file to an absolute path. Ask for it if the user did not say which file.
2. Pick `lang_out` from the user's request (language codes such as `zh`, `ja`, `en`). Use `lang_in: "auto"` unless the source language is clear.
3. Keep the defaults `service: "google"` and `kernel: "auto"` unless the user names a translation service (for example `deepl` or `openai:gpt-4o-mini`) or a kernel.
4. For long documents, ask whether to translate only some pages first and pass them as `pages`, for example `"1-3"`.
5. Report the two output paths the tool returns: the translated PDF (mono) and the bilingual PDF (dual).

If the MCP server is not available, run the command line instead and read its single JSON line from stdout:

```bash
uvx pdf2zh "<file>" -lo <lang> --json
```

// Command that starts pdf2zh. Use an absolute path when Zotero cannot find
// it on PATH, or a launcher such as "uvx pdf2zh".
pref("extensions.pdf2zh.command", "pdf2zh");
pref("extensions.pdf2zh.langIn", "en");
pref("extensions.pdf2zh.langOut", "zh");
// Translation service, optionally service:model, e.g. "openai:gpt-4o-mini".
pref("extensions.pdf2zh.service", "google");
// auto, babeldoc or legacy.
pref("extensions.pdf2zh.kernel", "auto");
// Reader: most pages translated by one pdf2zh run.
pref("extensions.pdf2zh.readerBatch", 4);

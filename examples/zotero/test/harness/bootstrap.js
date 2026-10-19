/* Test harness: runs only when PDF2ZH_TEST_OUT is set (see ../run-in-zotero.mjs).
 * Imports PDF2ZH_TEST_PDF, opens it in the reader, presses the pdf2zh button,
 * waits for translated pages, scrolls to the end, and writes report.json plus
 * PNGs of the overlays into PDF2ZH_TEST_OUT. Then quits Zotero. */

function install() {}
function shutdown() {}
function uninstall() {}

function startup() {
  const out = Services.env.get("PDF2ZH_TEST_OUT");
  const pdf = Services.env.get("PDF2ZH_TEST_PDF");
  // Zotero starts plugins one after another and waits for each startup(),
  // so run the test in the background and let the pdf2zh plugin start.
  if (out && pdf) run(out, pdf);
}

async function run(out, pdf) {
  await Zotero.initializationPromise;
  const report = { steps: [] };
  const step = (name, extra = {}) => report.steps.push({ name, t: Date.now(), ...extra });
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const waitFor = async (label, check, timeout) => {
    const end = Date.now() + timeout;
    for (;;) {
      const value = await check();
      if (value) return value;
      if (Date.now() > end) throw new Error(`timed out waiting for ${label}`);
      await sleep(500);
    }
  };
  try {
    await waitFor("main window", () => Zotero.getMainWindow()?.ZoteroPane, 60000);
    const item = await Zotero.Attachments.importFromFile({ file: pdf, libraryID: Zotero.Libraries.userLibraryID });
    step("imported", { itemID: item.id });
    const reader = await Zotero.Reader.open(item.id);
    await reader._initPromise;
    step("reader open");
    const readerDoc = reader._iframeWindow.document;
    const button = await waitFor("pdf2zh button", () => readerDoc.querySelector("[data-pdf2zh=toggle]"), 30000);
    button.click();
    step("button clicked");
    const view = reader._internalReader._primaryView._iframeWindow;
    const app = view.PDFViewerApplication;
    report.total = app.pagesCount;
    const done = () => [...view.document.querySelectorAll(".pdf2zh-layer")]
      .filter(l => l.dataset.state === "done" && l.querySelector("canvas"));
    const firstVisible = await waitFor("first translated page", () => done().length > 0 && done(), 300000);
    step("first page translated", { pages: firstVisible.map(l => l.parentElement.dataset.pageNumber) });
    app.pdfViewer.currentPageNumber = app.pagesCount;
    step("scrolled to last page");
    await waitFor("last page translated", () => done().some(l => l.parentElement.dataset.pageNumber === String(app.pagesCount)), 300000);
    step("last page translated");
    await sleep(1000);
    report.translatedPages = done().map(l => Number(l.parentElement.dataset.pageNumber)).sort((a, b) => a - b);
    for (const layer of done()) {
      const n = layer.parentElement.dataset.pageNumber;
      const png = layer.querySelector("canvas").toDataURL("image/png");
      await IOUtils.write(PathUtils.join(out, `page-${n}-translated.png`),
        Uint8Array.from(atob(png.split(",")[1]), c => c.charCodeAt(0)));
      const original = layer.parentElement.querySelector(".canvasWrapper canvas");
      if (original) {
        const opng = original.toDataURL("image/png");
        await IOUtils.write(PathUtils.join(out, `page-${n}-original.png`),
          Uint8Array.from(atob(opng.split(",")[1]), c => c.charCodeAt(0)));
      }
    }
    report.ok = true;
  } catch (e) {
    report.ok = false;
    report.error = `${e}\n${e && e.stack || ""}`;
  }
  await IOUtils.writeJSON(PathUtils.join(out, "report.json"), report);
  Zotero.Utilities.Internal.quit();
}

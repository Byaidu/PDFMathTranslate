/* Runs inside Zotero's pdf.js viewer (the reader's PDF iframe), injected by
 * reader.js. It reports which pages are visible and draws translated pages
 * over the originals. All pdf.js work stays here, in the page's own context;
 * the plugin talks to it with window.postMessage:
 *
 *   plugin -> page  { source: "pdf2zh-host", type: "mode", on, labels }
 *                   { source: "pdf2zh-host", type: "file", fileId, data }
 *                   { source: "pdf2zh-host", type: "page", page, fileId }
 *                   { source: "pdf2zh-host", type: "status", page, state }
 *   page -> plugin  { source: "pdf2zh-content", type: "visible", pages, total }
 */
(() => {
  if (window.__pdf2zhContent) return;
  window.__pdf2zhContent = true;

  const app = window.PDFViewerApplication;
  const files = new Map(); // fileId -> Promise<PDFDocumentProxy>
  const pages = new Map(); // page -> { state: "queued" | "failed" | "done", fileId? }
  let on = false;
  let labels = { queued: "Translating…", failed: "Translation failed" };
  let timer;

  const post = (message) => window.postMessage({ source: "pdf2zh-content", ...message }, "*");

  function visiblePages() {
    const views = app.pdfViewer?._getVisiblePages?.()?.views || [];
    return views.map(view => view.id);
  }

  function reportVisible() {
    if (!on) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      const visible = visiblePages();
      post({ type: "visible", pages: visible, total: app.pagesCount });
      for (const n of visible) draw(n);
    }, 150);
  }

  function layerOf(pageView, create) {
    let layer = pageView.div.querySelector(":scope > .pdf2zh-layer");
    if (!layer && create) {
      layer = document.createElement("div");
      layer.className = "pdf2zh-layer";
      Object.assign(layer.style, {
        position: "absolute", inset: "0", zIndex: "30", background: "#fff", pointerEvents: "none",
        display: "flex", alignItems: "center", justifyContent: "center",
        font: "13px system-ui, sans-serif", color: "#666",
      });
      pageView.div.append(layer);
    }
    return layer;
  }

  async function draw(n) {
    const pageView = app.pdfViewer?.getPageView(n - 1);
    if (!pageView?.div) return;
    const entry = pages.get(n);
    if (!on || !entry) {
      layerOf(pageView, false)?.remove();
      return;
    }
    const layer = layerOf(pageView, true);
    if (entry.state !== "done") {
      layer.dataset.state = entry.state;
      layer.dataset.key = "";
      layer.replaceChildren(entry.state === "failed" ? labels.failed : labels.queued);
      return;
    }
    const width = pageView.div.clientWidth;
    const height = pageView.div.clientHeight;
    const key = `${entry.fileId}|${width}x${height}`;
    if (layer.dataset.key === key) return;
    if (!files.has(entry.fileId)) return; // drawn when the file arrives
    layer.dataset.key = key;
    const doc = await files.get(entry.fileId);
    const page = await doc.getPage(n);
    const ratio = window.devicePixelRatio || 1;
    const viewport = page.getViewport({ scale: (width / page.getViewport({ scale: 1 }).width) * ratio });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    Object.assign(canvas.style, { width: `${width}px`, height: `${height}px`, display: "block" });
    await page.render({ canvas, canvasContext: canvas.getContext("2d"), viewport }).promise;
    if (layer.dataset.key !== key) return; // superseded by a newer draw
    layer.replaceChildren(canvas);
    layer.dataset.state = "done";
  }

  function redrawAll() {
    for (const n of pages.keys()) draw(n);
  }

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || data.source !== "pdf2zh-host") return;
    if (data.type === "mode") {
      on = data.on;
      if (data.labels) labels = data.labels;
      if (on) reportVisible();
      redrawAll();
    } else if (data.type === "file") {
      if (!files.has(data.fileId)) {
        files.set(data.fileId, window.pdfjsLib.getDocument({
          data: data.data, cMapUrl: "cmaps/", cMapPacked: true, standardFontDataUrl: "standard_fonts/",
        }).promise);
        for (const [n, entry] of pages) if (entry.fileId === data.fileId) draw(n);
      }
    } else if (data.type === "page") {
      pages.set(data.page, { state: "done", fileId: data.fileId });
      draw(data.page);
    } else if (data.type === "status") {
      if (data.state) pages.set(data.page, { state: data.state });
      else pages.delete(data.page); // withdrawn: no placeholder
      draw(data.page);
    }
  });

  app.eventBus.on("updateviewarea", reportVisible);
  // pdf.js re-renders a page after zooming or when it scrolls back into view.
  app.eventBus.on("pagerendered", (event) => draw(event.pageNumber));
})();

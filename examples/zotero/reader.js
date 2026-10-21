/* Translate pages in Zotero's PDF reader as they scroll into view.
 *
 * A toolbar button switches a reader into translation mode. content.js, injected
 * into the reader's pdf.js viewer, reports the visible pages; this file asks
 * pdf2zh for them and hands the results back for content.js to draw over the
 * originals.
 *
 * One translation runs at a time, in the resident pdf2zh worker (pdf2zh.js).
 * Pages requested while it runs are translated together in the next request
 * (pages "3,4,5"); pages that scrolled away before their turn are dropped.
 * Results are kept under the Zotero data directory, per file hash and
 * translation options, so reopening a PDF shows its translated pages at once.
 */

var PDF2ZH_READER = {
  PREFETCH: 2,
  states: new Map(), // reader instance id -> state
  queue: [], // { hash, file, key, options, page, waiters: Set<{ state, resolve, reject }> }
  running: false,

  init({ pluginID, contentScript }) {
    this.pluginID = pluginID;
    this.contentScript = contentScript;
    this._onToolbar = event => this.renderToolbar(event);
    Zotero.Reader.registerEventListener("renderToolbar", this._onToolbar, pluginID);
  },

  shutdown() {
    Zotero.Reader.unregisterEventListener("renderToolbar", this._onToolbar);
    for (const state of this.states.values()) this.setMode(state, false);
    this.states.clear();
    this.queue = [];
  },

  labels() {
    const zh = /^zh/i.test(Zotero.locale || "");
    return {
      button: zh ? "译" : "Tr",
      title: zh ? "用 pdf2zh 翻译页面" : "Translate pages with pdf2zh",
      queued: zh ? "翻译中…" : "Translating…",
      failed: zh ? "翻译失败" : "Translation failed",
    };
  },

  renderToolbar({ reader, doc, append }) {
    if (reader.type !== "pdf") return;
    const labels = this.labels();
    const button = doc.createElement("button");
    button.className = "toolbar-button pdf2zh-toggle";
    button.dataset.pdf2zh = "toggle";
    button.title = labels.title;
    button.textContent = labels.button;
    button.style.fontWeight = "600";
    button.addEventListener("click", async () => {
      try {
        const state = this.states.get(reader._instanceID) || await this.attach(reader);
        this.setMode(state, !state.on);
        button.classList.toggle("active", state.on);
        button.setAttribute("aria-pressed", String(state.on));
      } catch (e) {
        Zotero.logError(e);
      }
    });
    append(button);
  },

  /** Inject content.js into the reader's pdf.js viewer and start listening to it. */
  async attach(reader) {
    await reader._initPromise;
    const view = reader._internalReader._primaryView;
    const win = view._iframeWindow;
    await win.PDFViewerApplication.initializedPromise;
    if (!win.__pdf2zhContent) {
      const script = win.document.createElement("script");
      script.textContent = this.contentScript;
      win.document.documentElement.append(script);
    }
    const item = Zotero.Items.get(reader.itemID);
    const file = await item.getFilePathAsync();
    if (!file) throw new Error("The PDF file is missing");
    const state = {
      reader, win, file,
      hash: await Zotero.Utilities.Internal.md5Async(file),
      on: false,
      wanted: new Set(),
      requested: new Set(), // `${key}:${page}` already requested by this reader
      sent: new Map(), // result file -> Promise of sending it to this reader's viewer
    };
    win.addEventListener("message", event => this.onMessage(state, event));
    this.states.set(reader._instanceID, state);
    return state;
  },

  setMode(state, on) {
    state.on = on;
    if (!on) state.wanted = new Set();
    this.post(state, { type: "mode", on, labels: this.labels() });
  },

  post(state, message) {
    try {
      state.win.postMessage(Cu.cloneInto({ source: "pdf2zh-host", ...message }, state.win), "*");
    } catch (e) {
      // the reader was closed
      this.states.delete(state.reader._instanceID);
    }
  },

  options() {
    return {
      langIn: PDF2ZH.pref("langIn"),
      langOut: PDF2ZH.pref("langOut"),
      service: PDF2ZH.pref("service"),
      kernel: PDF2ZH.pref("kernel"),
    };
  },

  onMessage(state, event) {
    const data = Cu.waiveXrays(event.data);
    if (!data || data.source !== "pdf2zh-content" || data.type !== "visible" || !state.on) return;
    const visible = Array.from(data.pages, Number);
    const wanted = PDF2ZH.wantedPages(visible, Number(data.total) || 0, this.PREFETCH);
    state.wanted = new Set(wanted);
    for (const page of wanted) this.show(state, page);
  },

  /** Get one translated page to the reader: from the cache, or through the queue. */
  async show(state, page) {
    const options = this.options();
    const key = PDF2ZH.optionsKey(options);
    const tag = `${key}:${page}`;
    if (state.requested.has(tag)) return;
    state.requested.add(tag);
    try {
      let file = (await this.readIndex(state.hash, key))[page];
      if (file) file = PathUtils.join(this.cacheDir(state.hash, key), ...file.split("/"));
      if (!file || !(await IOUtils.exists(file))) {
        this.post(state, { type: "status", page, state: "queued" });
        file = await this.enqueue(state, options, key, page);
      }
      // Pages of one batch share a file: send it once, and send no page of it
      // before the file itself.
      if (!state.sent.has(file)) {
        state.sent.set(file, IOUtils.read(file).then(data => this.post(state, { type: "file", fileId: file, data })));
      }
      await state.sent.get(file);
      this.post(state, { type: "page", page, fileId: file });
    } catch (e) {
      state.requested.delete(tag);
      if (e?.withdrawn) {
        this.post(state, { type: "status", page, state: undefined });
        return;
      }
      Zotero.logError(e);
      this.post(state, { type: "status", page, state: "failed" });
    }
  },

  enqueue(state, options, key, page) {
    let job = this.queue.find(j => j.hash === state.hash && j.key === key && j.page === page);
    if (!job) {
      job = { hash: state.hash, file: state.file, key, options, page, waiters: new Set() };
      this.queue.push(job);
    }
    const promise = new Promise((resolve, reject) => job.waiters.add({ state, resolve, reject }));
    this.pump();
    return promise;
  },

  async pump() {
    if (this.running) return;
    // Drop pages nobody is looking at any more.
    for (const job of this.queue) {
      for (const waiter of job.waiters) {
        if (!waiter.state.wanted.has(job.page)) {
          job.waiters.delete(waiter);
          waiter.reject(Object.assign(new Error("withdrawn"), { withdrawn: true }));
        }
      }
    }
    this.queue = this.queue.filter(job => job.waiters.size > 0);
    if (this.queue.length === 0) return;

    this.running = true;
    const first = this.queue[0];
    const batch = this.queue
      .filter(j => j.hash === first.hash && j.key === first.key)
      .slice(0, Math.max(1, PDF2ZH.pref("readerBatch") || 4));
    this.queue = this.queue.filter(j => !batch.includes(j));
    const pages = batch.map(j => j.page).sort((a, b) => a - b);
    try {
      const run = `run-${Date.now()}`;
      const dir = PathUtils.join(this.cacheDir(first.hash, first.key), run);
      await IOUtils.makeDirectory(dir, { createAncestors: true });
      const result = await PDF2ZH.translate(PDF2ZH.translateParams(first.file, dir, { ...first.options, pages: pages.join(",") }));
      const mono = result.results?.[0]?.mono;
      if (!mono) throw new Error("pdf2zh returned no translated PDF");
      const index = await this.readIndex(first.hash, first.key);
      // pdf2zh may report a different spelling of the same directory
      // (/private/var vs /var on macOS), so record the run and file name.
      for (const page of pages) index[page] = `${run}/${PathUtils.filename(mono)}`;
      await IOUtils.writeJSON(this.indexPath(first.hash, first.key), index);
      for (const job of batch) for (const w of job.waiters) w.resolve(mono);
    } catch (e) {
      for (const job of batch) for (const w of job.waiters) w.reject(e);
    } finally {
      this.running = false;
      this.pump();
    }
  },

  cacheDir(hash, key) {
    return PathUtils.join(Zotero.DataDirectory.dir, "pdf2zh", hash, key);
  },

  indexPath(hash, key) {
    return PathUtils.join(this.cacheDir(hash, key), "index.json");
  },

  async readIndex(hash, key) {
    try {
      return await IOUtils.readJSON(this.indexPath(hash, key));
    } catch (e) {
      return {};
    }
  },
};

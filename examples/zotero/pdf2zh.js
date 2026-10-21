/* Translate Zotero PDF attachments with pdf2zh: whole files from the item
 * menu, and page by page in the PDF reader (reader.js).
 *
 * Translations go to one resident `pdf2zh --worker` process, started on first
 * use and stopped when idle or when the plugin shuts down, so Python and the
 * layout model load once. Its protocol (pdf2zh/worker.py) is one JSON object
 * per line: {"ready": true, "protocol": 1, ...} first, then one
 * {"id", "result"} or {"id", "error"} per {"id", "method", "params"} request.
 *
 * The helpers at the top, WorkerClient included, are plain JavaScript and are
 * unit-tested with Node (test.mjs); the rest needs Zotero.
 */

var PDF2ZH = {
  PREF: "extensions.pdf2zh.",
  MENU_ID: "pdf2zh-translate",

  // ---------------------------------------------------------------- helpers

  /** Split a command line such as `uvx pdf2zh` or `"C:\My Tools\pdf2zh.exe"`. */
  splitCommand(line) {
    const parts = [];
    const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
    let m;
    while ((m = re.exec(line || ""))) parts.push(m[1] ?? m[2] ?? m[3]);
    return parts;
  },

  /** Worker params for one translation; `options.pages` is "1,3-5". */
  translateParams(file, output, options) {
    return {
      file,
      output,
      lang_in: options.langIn || "en",
      lang_out: options.langOut || "zh",
      service: options.service || "google",
      kernel: options.kernel || "auto",
      ...(options.pages ? { pages: options.pages } : {}),
    };
  },

  /** Pages to translate in the reader: the visible ones, then `ahead` more. */
  wantedPages(visible, total, ahead) {
    if (visible.length === 0) return [];
    const pages = [...visible].sort((a, b) => a - b);
    const last = pages[pages.length - 1];
    for (let p = last + 1; p <= Math.min(total, last + ahead); p++) pages.push(p);
    return pages;
  },

  /** A directory-safe name for one set of translation options. */
  optionsKey(options) {
    return [options.langIn, options.langOut, options.service, options.kernel]
      .map(v => String(v || "").replace(/[^A-Za-z0-9.-]+/g, "_"))
      .join("--");
  },

  /** Client for one `pdf2zh --worker` process. `start(onLine, onExit)`
   * launches the process and resolves with { write(text), close() }; it calls
   * onLine(line) for each stdout line and onExit(code, stderrTail) once. The
   * process is started on demand, and again after it exits. */
  WorkerClient: class {
    constructor(start, { idleMs = 10 * 60 * 1000, readyTimeoutMs = 120 * 1000, timers = globalThis } = {}) {
      this.start = start;
      this.idleMs = idleMs;
      this.readyTimeoutMs = readyTimeoutMs;
      this.timers = timers;
      this.transport = null;
      this.ready = null;
      this.pending = new Map();
      this.nextId = 1;
      this.idleTimer = null;
    }

    async translate(params) {
      this.timers.clearTimeout(this.idleTimer);
      await this.ensure();
      const transport = this.transport;
      if (!transport) throw new Error("pdf2zh worker stopped");
      const id = this.nextId++;
      try {
        return await new Promise((resolve, reject) => {
          this.pending.set(id, { resolve, reject });
          transport.write(JSON.stringify({ id, method: "translate", params }) + "\n");
        });
      } finally {
        if (this.pending.size === 0 && this.idleMs) {
          this.timers.clearTimeout(this.idleTimer);
          this.idleTimer = this.timers.setTimeout(() => this.close(), this.idleMs);
        }
      }
    }

    ensure() {
      if (this.ready) return this.ready;
      let started = false;
      let settle;
      const ready = new Promise((resolve, reject) => {
        settle = (error) => {
          this.timers.clearTimeout(timer);
          error ? reject(error) : resolve();
        };
      });
      ready.catch(() => {});
      this.ready = ready;
      const timer = this.timers.setTimeout(() => {
        settle(new Error("pdf2zh --worker did not start in time"));
        this.close();
      }, this.readyTimeoutMs);

      const onLine = (line) => {
        let message;
        try {
          message = JSON.parse(line);
        } catch (e) {
          return; // not protocol output
        }
        if (!started) {
          if (!message || !message.ready) return;
          started = true;
          if (message.protocol !== 1) {
            settle(new Error(`pdf2zh worker speaks protocol ${message.protocol}; this plugin needs 1`));
            this.close();
          } else {
            settle();
          }
          return;
        }
        const entry = this.pending.get(message.id);
        if (!entry) return;
        this.pending.delete(message.id);
        if (message.error) {
          const error = new Error(message.error.message || "pdf2zh failed");
          error.cancelled = Boolean(message.error.cancelled);
          entry.reject(error);
        } else {
          entry.resolve(message.result);
        }
      };
      const onExit = (code, stderr) => {
        const last = String(stderr || "").trim().split("\n").pop();
        const error = /unrecognized arguments: .*--worker/.test(stderr || "")
          ? new Error("This pdf2zh is too old for the plugin: update pdf2zh to a version with --worker.")
          : new Error(`pdf2zh worker exited with ${code}${last ? `: ${last}` : ""}`);
        if (this.ready === ready) {
          this.ready = null;
          this.transport = null;
        }
        settle(error);
        this.failAll(error);
      };
      Promise.resolve()
        .then(() => this.start(onLine, onExit))
        .then((transport) => {
          if (this.ready === ready) this.transport = transport;
          else transport.close(); // closed while starting
        }, (error) => {
          if (this.ready === ready) this.ready = null;
          settle(error);
        });
      return ready;
    }

    /** Stop the worker: it exits when its stdin closes. */
    close() {
      this.timers.clearTimeout(this.idleTimer);
      const transport = this.transport;
      this.transport = null;
      this.ready = null;
      this.failAll(new Error("pdf2zh worker stopped"));
      transport?.close();
    }

    failAll(error) {
      const entries = [...this.pending.values()];
      this.pending.clear();
      for (const entry of entries) entry.reject(error);
    }
  },

  /** Extra directories where uv, pip and Homebrew put commands. GUI apps on
   * macOS start without the shell's PATH, so add them. */
  extraPath(home, isWin) {
    if (isWin) return [`${home}\\.local\\bin`, `${home}\\AppData\\Roaming\\Python\\Scripts`];
    return [`${home}/.local/bin`, "/opt/homebrew/bin", "/usr/local/bin"];
  },

  // ---------------------------------------------------------------- Zotero

  pref(name) {
    return Zotero.Prefs.get(this.PREF + name, true);
  },

  addToWindow(window) {
    const doc = window.document;
    const menu = doc.getElementById("zotero-itemmenu");
    if (!menu || doc.getElementById(this.MENU_ID)) return;
    const item = doc.createXULElement("menuitem");
    item.id = this.MENU_ID;
    item.setAttribute("label", "Translate PDF with pdf2zh");
    item.addEventListener("command", () => this.translateSelected(window));
    menu.appendChild(item);
    this._onShowing = () => {
      item.hidden = this.selectedPDFs(window).length === 0;
    };
    menu.addEventListener("popupshowing", this._onShowing);
  },

  removeFromWindow(window) {
    const doc = window.document;
    doc.getElementById(this.MENU_ID)?.remove();
    const menu = doc.getElementById("zotero-itemmenu");
    if (menu && this._onShowing) menu.removeEventListener("popupshowing", this._onShowing);
  },

  /** PDF attachments among the selected items and their children. */
  selectedPDFs(window) {
    const pdfs = [];
    for (const item of window.ZoteroPane.getSelectedItems()) {
      if (item.isPDFAttachment()) pdfs.push(item);
      else if (item.isRegularItem()) {
        for (const id of item.getAttachments()) {
          const child = Zotero.Items.get(id);
          if (child.isPDFAttachment()) pdfs.push(child);
        }
      }
    }
    return pdfs;
  },

  async translateSelected(window) {
    const progress = new Zotero.ProgressWindow({ closeOnClick: true });
    progress.changeHeadline("pdf2zh");
    progress.show();
    for (const attachment of this.selectedPDFs(window)) {
      const line = new progress.ItemProgress("attachmentPDF", attachment.getDisplayTitle());
      try {
        line.setText(`Translating ${attachment.getDisplayTitle()}…`);
        const added = await this.translateAttachment(attachment);
        line.setProgress(100);
        line.setText(`Added ${added} file(s) to ${attachment.getDisplayTitle()}`);
      } catch (e) {
        Zotero.logError(e);
        line.setError();
        line.setText(String(e.message || e));
      }
    }
    progress.startCloseTimer(8000);
  },

  async translateAttachment(attachment) {
    const file = await attachment.getFilePathAsync();
    if (!file) throw new Error("The PDF file is missing");
    const outputDir = PathUtils.join(
      Zotero.getTempDirectory().path,
      `pdf2zh-${Date.now()}-${attachment.key}`,
    );
    await IOUtils.makeDirectory(outputDir);
    try {
      const options = {
        langIn: this.pref("langIn"),
        langOut: this.pref("langOut"),
        service: this.pref("service"),
        kernel: this.pref("kernel"),
      };
      const result = await this.translate(this.translateParams(file, outputDir, options));
      let added = 0;
      for (const [kind, label] of [["dual", "bilingual"], ["mono", "translated"]]) {
        const path = result.results[0]?.[kind];
        if (!path) continue;
        await this.attach(attachment, path, `${attachment.getDisplayTitle()} (${options.langOut}, ${label})`);
        added++;
      }
      return added;
    } finally {
      await IOUtils.remove(outputDir, { recursive: true, ignoreAbsent: true });
    }
  },

  /** Store a PDF next to the source attachment. */
  async attach(source, path, title) {
    const parentItemID = source.parentID || undefined;
    const item = await Zotero.Attachments.importFromFile({
      file: path,
      libraryID: source.libraryID,
      parentItemID,
      collections: parentItemID ? undefined : source.getCollections(),
    });
    item.setField("title", title);
    await item.saveTx();
  },

  /** Translate with the resident worker; resolves with the `--json` result. */
  translate(params) {
    const command = this.pref("command") || "pdf2zh";
    if (this._worker && this._workerCommand !== command) this.stopWorker();
    if (!this._worker) {
      const timers = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
      this._worker = new this.WorkerClient((onLine, onExit) => this.startWorker(command, onLine, onExit), { timers });
      this._workerCommand = command;
    }
    return this._worker.translate(params);
  },

  stopWorker() {
    this._worker?.close();
    this._worker = null;
  },

  /** Start `<command> --worker` with Zotero's Subprocess module. */
  async startWorker(commandLine, onLine, onExit) {
    const { Subprocess } = ChromeUtils.importESModule(
      "resource://gre/modules/Subprocess.sys.mjs",
    );
    const { setTimeout } = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
    const [commandName, ...prefix] = this.splitCommand(commandLine);
    const sep = Zotero.isWin ? ";" : ":";
    const environment = Subprocess.getEnvironment();
    environment.PATH = [environment.PATH, ...this.extraPath(PathUtils.homeDir, Zotero.isWin)]
      .filter(Boolean)
      .join(sep);
    environment.PYTHONIOENCODING = "utf-8";
    const command = await Subprocess.pathSearch(commandName, environment).catch(() => {
      throw new Error(`Cannot find "${commandName}". Set the full path in pdf2zh's settings.`);
    });
    const proc = await Subprocess.call({
      command,
      arguments: [...prefix, "--worker"],
      environment,
      stdin: "pipe",
      stderr: "pipe",
    });

    // Read both pipes: pdf2zh logs a lot on stderr and would block on a full pipe.
    let stderr = "";
    const readStdout = async () => {
      let buffer = "";
      let chunk;
      while ((chunk = await proc.stdout.readString())) {
        buffer += chunk;
        let newline;
        while ((newline = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, newline).trim();
          buffer = buffer.slice(newline + 1);
          if (line) onLine(line);
        }
      }
    };
    const readStderr = async () => {
      let chunk;
      while ((chunk = await proc.stderr.readString())) stderr = (stderr + chunk).slice(-20000);
    };
    Promise.resolve().then(() =>
      Promise.all([readStdout(), readStderr(), proc.wait()]).then(
        ([, , { exitCode }]) => {
          if (exitCode) Zotero.debug(`pdf2zh worker exited with ${exitCode}:\n${stderr}`);
          onExit(exitCode, stderr);
        },
        (error) => onExit(String(error), stderr),
      ),
    );
    return {
      write: (text) => proc.stdin.write(text),
      close: () => {
        proc.stdin.close().catch(() => {});
        setTimeout(() => proc.kill(), 5000);
      },
    };
  },
};

if (typeof module !== "undefined") module.exports = PDF2ZH;

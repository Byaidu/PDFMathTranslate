/* Translate Zotero PDF attachments with pdf2zh.
 *
 * pdf2zh runs as a subprocess with --json, which prints exactly one JSON line
 * on stdout ({"ok": true, "results": [{"mono": ..., "dual": ...}]}) and keeps
 * logs on stderr. No server has to be kept running.
 *
 * The helpers at the top are plain JavaScript and are unit-tested with Node
 * (test.mjs); the rest needs Zotero.
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

  /** Arguments after the command for one translation. */
  buildArgs(file, outputDir, options) {
    return [
      file,
      "--lang-in", options.langIn || "en",
      "--lang-out", options.langOut || "zh",
      "--service", options.service || "google",
      "--kernel", options.kernel || "auto",
      "--output", outputDir,
      "--json",
    ];
  },

  /** The result object from pdf2zh --json stdout. */
  parseResult(stdout) {
    const lines = String(stdout).trim().split(/\r?\n/).reverse();
    for (const line of lines) {
      if (!line.startsWith("{")) continue;
      try {
        const result = JSON.parse(line);
        if (typeof result.ok === "boolean") return result;
      } catch (e) {
        // not the result line
      }
    }
    throw new Error("pdf2zh printed no result; update pdf2zh to a version with --json");
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
      const result = await this.run(this.buildArgs(file, outputDir, options));
      if (!result.ok) throw new Error(result.error || "pdf2zh failed");
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

  /** Run pdf2zh and return its parsed --json result. */
  async run(args) {
    const { Subprocess } = ChromeUtils.importESModule(
      "resource://gre/modules/Subprocess.sys.mjs",
    );
    const [commandName, ...prefix] = this.splitCommand(this.pref("command") || "pdf2zh");
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
      arguments: [...prefix, ...args],
      environment,
      stderr: "pipe",
    });
    // Read both pipes: pdf2zh logs a lot on stderr and would block on a full pipe.
    const readAll = async (pipe) => {
      let text = "";
      let chunk;
      while ((chunk = await pipe.readString())) text += chunk;
      return text;
    };
    const [stdout, stderr] = await Promise.all([readAll(proc.stdout), readAll(proc.stderr)]);
    const { exitCode } = await proc.wait();
    try {
      return this.parseResult(stdout);
    } catch (e) {
      Zotero.debug(`pdf2zh exited with ${exitCode}:\n${stderr}`);
      throw new Error(`pdf2zh exited with ${exitCode}: ${stderr.trim().split("\n").pop() || e.message}`);
    }
  },
};

if (typeof module !== "undefined") module.exports = PDF2ZH;

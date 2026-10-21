/* Zotero 7+ bootstrap entry points. The work happens in pdf2zh.js (item menu)
 * and reader.js (translation inside the PDF reader). */

var PDF2ZH;
var PDF2ZH_READER;

function install() {}

async function startup({ id, rootURI }) {
  await Zotero.initializationPromise;
  Services.scriptloader.loadSubScript(rootURI + "pdf2zh.js");
  Services.scriptloader.loadSubScript(rootURI + "reader.js");
  const contentScript = await (await fetch(rootURI + "content.js")).text();
  PDF2ZH_READER.init({ pluginID: id, contentScript });
  Zotero.PreferencePanes.register({
    pluginID: id,
    src: rootURI + "prefs.xhtml",
    label: "pdf2zh",
  });
  for (const window of Zotero.getMainWindows()) PDF2ZH.addToWindow(window);
}

function onMainWindowLoad({ window }) {
  PDF2ZH?.addToWindow(window);
}

function onMainWindowUnload({ window }) {
  PDF2ZH?.removeFromWindow(window);
}

function shutdown() {
  PDF2ZH_READER?.shutdown();
  PDF2ZH?.stopWorker();
  for (const window of Zotero.getMainWindows()) PDF2ZH?.removeFromWindow(window);
  PDF2ZH = undefined;
  PDF2ZH_READER = undefined;
}

function uninstall() {}

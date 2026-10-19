/* Zotero 7+ bootstrap entry points. The work happens in pdf2zh.js. */

var PDF2ZH;

function install() {}

async function startup({ id, rootURI }) {
  await Zotero.initializationPromise;
  Services.scriptloader.loadSubScript(rootURI + "pdf2zh.js");
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
  for (const window of Zotero.getMainWindows()) PDF2ZH?.removeFromWindow(window);
  PDF2ZH = undefined;
}

function uninstall() {}

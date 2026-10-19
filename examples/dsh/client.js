// Browser half of dsh-pdf2zh: a PDF reader for dsh's right-sidebar document
// preview that translates pages on demand as they scroll into view.
//
// Hand-written in the module format dsh serves to the browser
// (window.__ModuleLoader__.load with a CommonJS-style factory), so it needs no
// build step. React comes from dsh's shared modules; pdf.js is loaded on first
// use from this plugin's /pdf2zh/pdfjs route (see viewer.js).

window.__ModuleLoader__.load({
  id: 'dsh-pdf2zh',
  factory: (require) => {
    var module = { exports: {} }
    var exports = module.exports
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })

    const React = require('react')
    const h = React.createElement
    const { useCallback, useEffect, useMemo, useRef, useState } = React

    const READER_ID = 'dsh-pdf2zh/reader'
    const PREFETCH = 2 // pages past the viewport to translate ahead
    const ZH = typeof navigator !== 'undefined' && /^zh/i.test(navigator.language || '')
    const T = ZH
      ? {
          title: 'PDF 翻译', original: '原文', translated: '译文', split: '对照', auto: '自动翻译',
          translateVisible: '翻译可见页', done: '已翻译', loading: '加载中…', translating: '翻译中…',
          queued: '排队中', failed: '翻译失败，点击重试', notLoaded: '无法加载 PDF',
        }
      : {
          title: 'PDF translate', original: 'Original', translated: 'Translated', split: 'Side by side',
          auto: 'Auto-translate', translateVisible: 'Translate visible pages', done: 'Translated',
          loading: 'Loading…', translating: 'Translating…', queued: 'Queued',
          failed: 'Translation failed, click to retry', notLoaded: 'Cannot load the PDF',
        }
    const LANGUAGES = [['zh', '中文'], ['en', 'English'], ['ja', '日本語'], ['ko', '한국어'],
      ['fr', 'Français'], ['de', 'Deutsch'], ['es', 'Español'], ['ru', 'Русский']]

    // ---------------------------------------------------------- helpers

    /** Root URL of this plugin's routes, honouring a <base> mount. */
    function routeRoot() {
      const base = document.querySelector('base')
      return base ? new URL('pdf2zh/', base.href) : new URL('/pdf2zh/', location.origin)
    }

    let pdfjsPromise
    function loadPdfjs() {
      if (!pdfjsPromise) {
        const root = routeRoot()
        pdfjsPromise = import(new URL('pdfjs/build/pdf.min.mjs', root).href).then((pdfjs) => {
          pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs/build/pdf.worker.min.mjs', root).href
          return pdfjs
        })
        pdfjsPromise.catch(() => { pdfjsPromise = undefined })
      }
      return pdfjsPromise
    }

    async function openPdf(bytes) {
      const pdfjs = await loadPdfjs()
      const root = routeRoot()
      return pdfjs.getDocument({
        data: bytes,
        cMapUrl: new URL('pdfjs/cmaps/', root).href,
        cMapPacked: true,
        standardFontDataUrl: new URL('pdfjs/standard_fonts/', root).href,
        wasmUrl: new URL('pdfjs/wasm/', root).href,
      }).promise
    }

    async function api(path, init) {
      const response = await fetch(new URL(path, routeRoot()), {
        ...init, headers: { 'x-pdf2zh': '1', ...(init && init.headers) },
      })
      if (!response.ok) {
        let message = `${response.status}`
        try { message = (await response.json()).error || message } catch {}
        throw new Error(message)
      }
      return response
    }

    /** Pages to translate: visible ones first, then a few ahead. */
    function wantedPages(visible, total, ahead) {
      if (visible.length === 0) return []
      const sorted = [...visible].sort((a, b) => a - b)
      const last = sorted[sorted.length - 1]
      for (let p = last + 1; p <= Math.min(total, last + ahead); p++) sorted.push(p)
      return sorted
    }
    exports.wantedPages = wantedPages

    // ---------------------------------------------------------- page canvas

    /** Render one pdf.js page to a canvas at the given CSS width. */
    function PageCanvas({ doc, number, width }) {
      const canvas = useRef(null)
      useEffect(() => {
        if (!doc || !width) return
        let task
        let cancelled = false
        doc.getPage(number).then((page) => {
          if (cancelled || !canvas.current) return
          const scale = width / page.getViewport({ scale: 1 }).width
          const ratio = window.devicePixelRatio || 1
          const viewport = page.getViewport({ scale: scale * ratio })
          const el = canvas.current
          el.width = Math.floor(viewport.width)
          el.height = Math.floor(viewport.height)
          el.style.width = `${width}px`
          el.style.height = `${viewport.height / ratio}px`
          task = page.render({ canvas: el, canvasContext: el.getContext('2d'), viewport })
          task.promise.catch(() => {})
        })
        return () => { cancelled = true; task?.cancel() }
      }, [doc, number, width])
      return h('canvas', { ref: canvas, style: { display: 'block', background: '#fff' } })
    }

    function Placeholder({ width, height, text, onClick }) {
      return h('div', {
        onClick,
        style: {
          width, height, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(127,127,127,.08)', color: 'inherit', opacity: 0.7, fontSize: 13,
          cursor: onClick ? 'pointer' : 'default',
        },
      }, text)
    }

    // ---------------------------------------------------------- reader

    function Reader(props) {
      const data = props.content && props.content.kind === 'bytes' ? props.content.data : undefined
      const [source, setSource] = useState() // { doc, sizes }
      const [docId, setDocId] = useState()
      const [error, setError] = useState()
      const [mode, setMode] = useState('split')
      const [auto, setAuto] = useState(true)
      const [langOut, setLangOut] = useState()
      const [pages, setPages] = useState({}) // key `${lang}:${n}` -> { state, doc?, error? }
      const [visible, setVisible] = useState([])
      const [width, setWidth] = useState(0)
      const scroller = useRef(null)
      const requests = useRef(new Map()) // key -> AbortController

      // Default target language from the plugin settings.
      useEffect(() => {
        api('config', { method: 'GET' }).then(r => r.json())
          .then(config => setLangOut(prev => prev || config.langOut || 'zh'))
          .catch(() => setLangOut(prev => prev || 'zh'))
      }, [])

      // Open the original and register it with the host.
      useEffect(() => {
        if (!data) return
        let cancelled = false
        setSource(undefined); setDocId(undefined); setError(undefined); setPages({})
        openPdf(data.slice()).then(async (doc) => {
          const sizes = []
          for (let n = 1; n <= doc.numPages; n++) {
            const viewport = (await doc.getPage(n)).getViewport({ scale: 1 })
            sizes.push({ width: viewport.width, height: viewport.height })
          }
          if (!cancelled) setSource({ doc, sizes })
        }).catch(e => { if (!cancelled) setError(e.message || String(e)) })
        api('documents', { method: 'POST', body: data })
          .then(r => r.json()).then(({ id }) => { if (!cancelled) setDocId(id) })
          .catch(e => { if (!cancelled) setError(e.message || String(e)) })
        return () => { cancelled = true }
      }, [data])

      // Track the scroller width for page sizing.
      useEffect(() => {
        const el = scroller.current
        if (!el) return
        const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
        observer.observe(el)
        return () => observer.disconnect()
      }, [])

      // Track which pages are on screen.
      useEffect(() => {
        const el = scroller.current
        if (!el || !source) return
        const shown = new Set()
        const observer = new IntersectionObserver((entries) => {
          for (const entry of entries) {
            const n = Number(entry.target.dataset.page)
            if (entry.isIntersecting) shown.add(n)
            else shown.delete(n)
          }
          setVisible([...shown].sort((a, b) => a - b))
        }, { root: el, rootMargin: '200px 0px' })
        el.querySelectorAll('[data-page]').forEach(node => observer.observe(node))
        return () => observer.disconnect()
      }, [source])

      const translate = useCallback((n) => {
        if (!docId || !langOut) return
        const key = `${langOut}:${n}`
        if (requests.current.has(key)) return
        const controller = new AbortController()
        requests.current.set(key, controller)
        setPages(prev => ({ ...prev, [key]: { state: 'queued' } }))
        api(`documents/${docId}/pages/${n}?lang_out=${encodeURIComponent(langOut)}`, {
          method: 'POST', signal: controller.signal,
        })
          .then(r => r.arrayBuffer())
          .then(buffer => openPdf(new Uint8Array(buffer)))
          .then(doc => setPages(prev => ({ ...prev, [key]: { state: 'done', doc } })))
          .catch((e) => {
            requests.current.delete(key)
            setPages(prev => ({
              ...prev, [key]: controller.signal.aborted ? undefined : { state: 'failed', error: e.message },
            }))
          })
      }, [docId, langOut])

      // Request visible pages and a few ahead; withdraw requests that left the window.
      useEffect(() => {
        if (!auto || !source || !docId || !langOut || mode === 'original') return
        const wanted = new Set(wantedPages(visible, source.doc.numPages, PREFETCH).map(n => `${langOut}:${n}`))
        for (const key of wanted) {
          const entry = pages[key]
          if (!entry || entry.state === undefined) translate(Number(key.split(':')[1]))
        }
        for (const [key, controller] of requests.current) {
          if (!wanted.has(key) && pages[key] && pages[key].state === 'queued') {
            controller.abort()
            requests.current.delete(key)
          }
        }
      }, [auto, visible, source, docId, langOut, mode, pages, translate])

      // Abort everything when the tab closes.
      useEffect(() => () => { for (const c of requests.current.values()) c.abort() }, [])

      const total = source ? source.doc.numPages : 0
      const doneCount = useMemo(
        () => Object.entries(pages).filter(([k, v]) => v && v.state === 'done' && k.startsWith(`${langOut}:`)).length,
        [pages, langOut])

      const columns = mode === 'split' ? 2 : 1
      const pageWidth = Math.max(0, Math.floor((width - 24 - (columns - 1) * 8) / columns))

      const button = (active, label, onClick) => h('button', {
        onClick,
        style: {
          padding: '3px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer', color: 'inherit',
          border: '1px solid rgba(127,127,127,.35)',
          background: active ? 'rgba(127,127,127,.22)' : 'transparent',
        },
      }, label)

      const toolbar = h('div', {
        style: {
          display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, padding: '8px 12px',
          borderBottom: '1px solid rgba(127,127,127,.2)', fontSize: 12,
        },
      },
      button(mode === 'original', T.original, () => setMode('original')),
      button(mode === 'translated', T.translated, () => setMode('translated')),
      button(mode === 'split', T.split, () => setMode('split')),
      h('select', {
        value: langOut || 'zh', onChange: e => setLangOut(e.target.value),
        style: { fontSize: 12, color: 'inherit', background: 'transparent', borderRadius: 6, padding: '2px 4px' },
      }, LANGUAGES.map(([code, label]) => h('option', { key: code, value: code }, label))),
      h('label', { style: { display: 'flex', alignItems: 'center', gap: 4 } },
        h('input', { type: 'checkbox', checked: auto, onChange: e => setAuto(e.target.checked) }), T.auto),
      auto ? null : button(false, T.translateVisible, () => visible.forEach(translate)),
      h('span', { style: { marginLeft: 'auto', opacity: 0.7 } }, total ? `${T.done} ${doneCount}/${total}` : ''))

      const translatedView = (n, size) => {
        const entry = pages[`${langOut}:${n}`]
        const height = pageWidth * size.height / size.width
        if (entry && entry.state === 'done') return h(PageCanvas, { doc: entry.doc, number: 1, width: pageWidth })
        if (entry && entry.state === 'failed') {
          return h(Placeholder, {
            width: pageWidth, height, text: T.failed,
            onClick: () => { requests.current.delete(`${langOut}:${n}`); translate(n) },
          })
        }
        return h(Placeholder, {
          width: pageWidth, height,
          text: entry && entry.state === 'queued' ? T.translating : (auto ? T.queued : ''),
        })
      }

      const near = (n) => visible.length > 0 && n >= visible[0] - 2 && n <= visible[visible.length - 1] + 2

      const body = error
        ? h('div', { style: { padding: 16 } }, `${T.notLoaded}: ${error}`)
        : !source
            ? h('div', { style: { padding: 16, opacity: 0.7 } }, T.loading)
            : source.sizes.map((size, i) => {
              const n = i + 1
              const height = pageWidth * size.height / size.width
              const original = near(n)
                ? h(PageCanvas, { doc: source.doc, number: n, width: pageWidth })
                : h(Placeholder, { width: pageWidth, height })
              const translated = near(n) ? translatedView(n, size) : h(Placeholder, { width: pageWidth, height })
              return h('div', {
                key: n, 'data-page': n,
                style: { display: 'flex', gap: 8, justifyContent: 'center', margin: '12px 12px 0' },
              },
              mode !== 'translated' ? original : null,
              mode !== 'original' ? translated : null)
            })

      return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
        toolbar,
        h('div', { ref: scroller, style: { flex: 1, minHeight: 0, overflow: 'auto', paddingBottom: 12 } }, body))
    }

    // ---------------------------------------------------------- plugin

    exports.name = 'pdf2zh-reader'
    exports.inject = ['slots', 'documentPreviews']
    exports.apply = function apply(ctx) {
      ctx.effect(() => ctx.documentPreviews.register({
        id: READER_ID,
        extensions: ['pdf'],
        binaryExtensions: ['pdf'],
        priority: 'extension',
        title: () => T.title,
        loading: 'bytes-complete',
        wrap: false,
      }))
      ctx.effect(() => ctx.slots.inject('sidebar.right.tab.document', () => ctx.slots.register({
        name: 'sidebar.right.tab.document', key: READER_ID,
      }, Reader)))
    }

    return module.exports
  },
})

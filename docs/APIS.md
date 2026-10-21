[**Documentation**](https://github.com/Byaidu/PDFMathTranslate) > **API Details** _(current)_

<h2 id="toc">Table of Content</h2>
- [Functional calls in Python](#api-python)
- [HTTP](#api-http)

---

<h2 id="api-python">Python</h2>

As `pdf2zh` is an installed module in Python, we expose two methods for other programs to call in any Python scripts.

For example, if you want translate a document from English to Chinese using Google Translate, you may use the following code:

```python
from pdf2zh import translate, translate_stream

params = {
    'lang_in': 'en',
    'lang_out': 'zh',
    'service': 'google',
    'thread': 4,
}
```
Translate with files:
```python
(file_mono, file_dual) = translate(files=['example.pdf'], **params)[0]
```
Translate with stream:
```python
with open('example.pdf', 'rb') as f:
    (stream_mono, stream_dual) = translate_stream(stream=f.read(), **params)
```

[⬆️ Back to top](#toc)

---

<h2 id="api-http">HTTP</h2>

The Flask/Celery backend (`pdf2zh --flask`, `pdf2zh --celery`) has been removed. For an HTTP service, start from the [example server](../examples/server/): REST with live progress over SSE, and a remote MCP endpoint, with no Redis. Plugins that run on the user's machine should use `pdf2zh --worker` instead ([protocol](../examples/README.md#pdf2zh---worker)).

[⬆️ Back to top](#toc)

---

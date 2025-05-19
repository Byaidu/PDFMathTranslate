<h2 id="toc">Table of Content</h2>
The present project supports two types of APIs, All methods need the Redis;

- [Functional calls in Python](#api-python)
- [HTTP protocols](#api-http)

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

In a more flexible way, you can communicate with the program using HTTP protocols, if:

1. Install and run backend

   ```bash
   pip install pdf2zh[backend]
   pdf2zh --flask
   pdf2zh --celery worker
   ```

2. Using HTTP protocols as follows:

   - Submit translate task

     ```bash
     curl http://localhost:11008/v1/translate -F "file=@example.pdf" -F "data={\"lang_in\":\"en\",\"lang_out\":\"zh\",\"service\":\"google\",\"thread\":4}"
     {"id":"d9894125-2f4e-45ea-9d93-1a9068d2045a"}
     ```

   - Check Progress

     ```bash
     curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a
     {"info":{"n":13,"total":506},"state":"PROGRESS"}
     ```

   - Check Progress _(if finished)_

     ```bash
     curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a
     {"state":"SUCCESS"}
     ```

   - Save monolingual file

     ```bash
     curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a/mono --output example-mono.pdf
     ```

   - Save bilingual file

     ```bash
     curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a/dual --output example-dual.pdf
     ```

   - Interrupt if running and delete the task
     ```bash
     curl http://localhost:11008/v1/translate/d9894125-2f4e-45ea-9d93-1a9068d2045a -X DELETE
     ```

[⬆️ Back to top](#toc)

---

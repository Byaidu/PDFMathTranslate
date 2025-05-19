[**Getting Started**](./getting-started.md) > **Installation** > **WebUI** _(current)_

---

### Use PDFMathTranslate via Webui

#### How to open the WebUI page:

There are several methods to open the WebUI interface. If you are using **Windows**, please refer to [this article](./INSTALLATION_winexe.md);

1. Python installed (3.10 <= version <= 3.12)

2. Install our package:

3. Start using in browser:

    ```bash
    pdf2zh -i
    ```

4. If your browswer has not been started automatically, goto

    ```bash
    http://localhost:7860/
    ```

    Drop the PDF file into the window and click `Translate`.

<img src="./images/gui.gif" width="500"/>

### Environment Variables

You can set the source and target languages using environment variables:

- `PDF2ZH_LANG_FROM`: Sets the source language. Defaults to "English".
- `PDF2ZH_LANG_TO`: Sets the target language. Defaults to "Simplified Chinese".

### Supported Languages

The following languages are supported:

- English
- Simplified Chinese
- Traditional Chinese
- French
- German
- Japanese
- Korean
- Russian
- Spanish
- Italian
- Portuguese

## Preview

<img src="./images/before.png" width="500"/>
<img src="./images/after.png" width="500"/>

## Maintainance

GUI maintained by [Rongxin](https://github.com/reycn)

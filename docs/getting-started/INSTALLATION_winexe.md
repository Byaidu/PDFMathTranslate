[**Getting Started**](./getting-started.md) > **Installation** > **Windows EXE** _(current)_

---

### Install PDFMathTranslate via .exe file

1. Download `pdf2zh-<version>-with-assets-win64.zip` from [release page](https://github.com/Byaidu/PDFMathTranslate/releases). 

    > [!TIP]
    > **What is the difference between `pdf2zh-<version>-with-assets-win64.zip` and `pdf2zh-<version>-win64.zip`?**
    >
    > - If you are downloading and using PDFMathTranslate for the first time, it is recommended to download `pdf2zh-<version>-with-assets-win64.zip`.
    > - The `pdf2zh-<version>-with-assets-win64.zip` includes resource files (such as fonts and models) compared to `pdf2zh-<version>-win64.zip`.
    > - The version without assets will also dynamically download resources when running, but the download may fail due to network issues.

2. Unzip `pdf2zh-<version>-with-assets-win64.zip` and navigate `pdf2zh` folder.
<br>
It takes a while to decompress, please be patient.

3. Navigate `pdf2zh/build` folder, then Double-click `pdf2zh.exe`。

    > [!TIP]
    > **Cannot run the .exe file**
    >
    > If you have some problems running pdf2zh.exe, please install `https://aka.ms/vs/17/release/vc_redist.x64.exe` and try again.

4. A terminal will pop up after double-clicking the exe file. After about half a minute to a minute, a webpage will open in your default browser. 
<br>
If it does not open, you can try to manually access `http://localhost:7860/`.

    > [!NOTE]
    >
    > If you encounter any issues during use WebUI, please refer to [this webpage](./USAGE_webui.md).

5. Enjoy!

> [!TIP]
> **You can use the .exe file via command line**
>
> Use the .exe file through command line as follows:
>
> 1. Launch your terminal and navigate to the folder containing the .exe file:
>
>    ```bash
>    cd /path/pdf2zh/build
>    ```
>
> 2. Call the .exe file:
>
>    ```bash
>    ./pdf2zh.exe "document.pdf"
>    ```
>
> You can use other command line parameters as normal:
>
> ```bash
> ./pdf2zh.exe "document.pdf" --lang-in en --lang-out ja
> ```
>
> If you need more information about command line usage, please refer to this article.

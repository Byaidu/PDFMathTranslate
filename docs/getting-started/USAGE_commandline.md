### Use PDFMathTranslate via command line

### Basic Usage

After Installation, please enter this command to translate your PDF.

```bash
pdf2zh document.pdf
```

After execute translation, files generated in *current working directory*.

??? tip "Where is my "Current Working Directory"? "

    Before entering a command in the terminal, you might see a pathname displayed in your terminal:
 
    ```bash
    PS C:\Users\XXX>
    ```
 
    This directory is the "*Current working directory*."
 
    If there is no pathname, try running this command in the terminal:
 
    ```bash
    pwd
    ```
 
    After executing this command, a pathname will be output. This pathname is the "*Current working directory*". The translated files will appear here.


!!! note

    If your pathname contains spaces, please enclose it in quotation marks.
 
    ```bash
    pdf2zh "path with spaces/document.pdf"
    ```

!!! warning

    - If you're using Windows and cannot open the file after downloading, please install [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) and try again.
 
    - If you cannot access Docker Hub, please try the image on [GitHub Container Registry](https://github.com/Byaidu/PDFMathTranslate/pkgs/container/pdfmathtranslate).
    
    ```bash
    docker pull ghcr.io/byaidu/pdfmathtranslate
    docker run -d -p 7860:7860 ghcr.io/byaidu/pdfmathtranslate
    ```
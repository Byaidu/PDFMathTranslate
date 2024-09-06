# PDFMathTranslate

Latex PDF 翻译及双语对照，保留公式和图标排版

## 安装

```bash
pip install pdf2zh
```

## 使用

命令行中执行翻译指令，在当前目录下生成中文文档 `example-zh.pdf` 以及双语文档 `example-dual.pdf` 

### 翻译完整文档

```bash
pdf2zh example.pdf
```

### 翻译部分文档

```bash
pdf2zh example.pdf --page-numbers 1 2 3
```

## 致谢

文档合并：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)

文档解析：[pdfminer.six](https://github.com/pdfminer/pdfminer.six)

多线程翻译：[MathTranslate](https://github.com/SUSYUSTC/MathTranslate)
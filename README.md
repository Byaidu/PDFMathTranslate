# PDFMathTranslate

<p align="center">
  <!-- PyPI -->
  <a href="https://pypi.org/project/pdf2zh/">
    <img src="https://img.shields.io/pypi/v/pdf2zh"/>
  </a>
  <!-- License -->
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Byaidu/PDFMathTranslate"/>
  </a>
</p>

基于字体规则的 Latex PDF 翻译及双语对照，保留公式和图表排版

![image](https://github.com/user-attachments/assets/57e1cde6-c647-4af8-8f8f-587a40050dde)

![image](https://github.com/user-attachments/assets/25086601-c90a-40e3-bf30-1556f2f919ec)


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
pdf2zh example.pdf -p 1 2 3
```

### 使用正则表达式指定需要保留样式的公式字体和字符

```bash
pdf2zh BDA3.pdf -f ".*\+(CM[^R].*|MS.*|XY.*|.*0700|.*0500)" -c "(\(|\||\)|\+|=|\d|[\u0080-\uffff])"
```

## 致谢

文档合并：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)

文档解析：[pdfminer.six](https://github.com/pdfminer/pdfminer.six)

多线程翻译：[MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

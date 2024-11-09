[English](README.md) | 简体中文

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
  <a href="https://t.me/+kXx8BQCnUTc3NDM9">
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=flat-squeare&logo=telegram&logoColor=white"/>
  </a>
</p>

PDF 文档翻译及双语对照

- 📊 保留公式和图表

- 📄 保留可索引目录

- 🌐 支持多种翻译服务

## 安装

要求 Python 版本 >=3.8, <=3.11

```bash
pip install -U "pdf2zh>=1.5.3"
```

## 使用

命令行中执行翻译指令，在工作目录下生成翻译文档 `example-zh.pdf` 和双语对照文档 `example-dual.pdf`。

### 翻译完整文档

```bash
pdf2zh example.pdf
```

### 翻译部分文档

```bash
pdf2zh example.pdf -p 1-3,5
```

### 使用指定语言翻译

参考 [Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages)

```bash
pdf2zh example.pdf -li en -lo ja
```

### 使用 Ollama 翻译

参考 [Ollama](https://github.com/ollama/ollama)

```bash
pdf2zh example.pdf -s gemma2
```

### 使用 DeepLX 翻译

参考 [DeepLX](https://github.com/OwO-Network/DeepLX)

1. 设置环境变量构建 endpoint：`{DEEPLX_URL}/{DEEPLX_TOKEN}/translate`:
   - `DEEPLX_URL`, e.g., `export DEEPLX_URL=https://api.deeplx.org`
   - `DEEPLX_TOKEN`, e.g., `export DEEPLX_TOKEN=ABCDEFG`

2. 执行:
```bash
pdf2zh example.pdf -s deeplx
```

### 使用正则表达式指定需要保留样式的字体和字符

```bash
pdf2zh example.pdf -f "(CM[^RT].*|MS.*|.*Ital)" -c "(\(|\||\)|\+|=|\d|[\u0080-\ufaff])"
```

## 预览

![image](https://github.com/user-attachments/assets/57e1cde6-c647-4af8-8f8f-587a40050dde)

![image](https://github.com/user-attachments/assets/0e6d7e44-18cd-443a-8a84-db99edf2c268)

![image](https://github.com/user-attachments/assets/5fe6af83-2f5b-47b1-9dd1-4aee6bc409de)

## 致谢

文档合并: [PyMuPDF](https://github.com/pymupdf/PyMuPDF)

文档解析: [Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

文档提取: [MinerU](https://github.com/opendatalab/MinerU)

多线程翻译: [MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

布局解析: [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

文档标准: [PDF Explained](https://zxyle.github.io/PDF-Explained/), [PDF Cheat Sheets](https://pdfa.org/resource/pdf-cheat-sheets/)

## Star History

<a href="https://star-history.com/#Byaidu/PDFMathTranslate&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
 </picture>
</a>

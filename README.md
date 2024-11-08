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

PDF scientific paper translation and bilingual comparison.

- 📊 Retain formulas and charts.

- 📄 Preserve table of contents.

- 🌐 Support multiple translation services.

## Installation

Require Python version >=3.8, <=3.11

```bash
pip install -U "pdf2zh>=1.5.3"
```

## Usage

Execute the translation command in the command line to generate the translated document `example-zh.pdf` and the bilingual document `example-dual.pdf` in the current directory.

### Translate the entire document

```bash
pdf2zh example.pdf
```

### Translate part of the document

```bash
pdf2zh example.pdf -p 1-3,5
```

### Translate with the specified language

See [Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages).

```bash
pdf2zh example.pdf -li en -lo ja
```

### Translate with Ollama

See [Ollama](https://github.com/ollama/ollama).

```bash
pdf2zh example.pdf -s gemma2
```

### Translate with DeepLX

See [DeepLX](https://github.com/OwO-Network/DeepLX).

1. Set ENVs to construct an endpoint like `{DEEPLX_URL}/{DEEPLX_TOKEN}/translate`:
   - `DEEPLX_URL`, e.g., `export DEEPLX_URL=https://api.deeplx.org`
   - `DEEPLX_TOKEN`, e.g., `export DEEPLX_TOKEN=ABCDEFG`

2. Run:
```bash
pdf2zh example.pdf -s deeplx
```

### Use regex to specify formula fonts and characters that need to be preserved

```bash
pdf2zh BDA3.pdf -f "(CM[^RT].*|MS.*|XY.*|MT.*|BL.*|.*0700|.*0500|.*Italic)" -c "(\(|\||\)|\+|=|\d|[\u0080-\ufaff])"
```

## Preview

![image](https://github.com/user-attachments/assets/57e1cde6-c647-4af8-8f8f-587a40050dde)

![image](https://github.com/user-attachments/assets/0e6d7e44-18cd-443a-8a84-db99edf2c268)

![image](https://github.com/user-attachments/assets/5fe6af83-2f5b-47b1-9dd1-4aee6bc409de)

## Acknowledgement

Document merging: [PyMuPDF](https://github.com/pymupdf/PyMuPDF)

Document parsing: [Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

Document extraction: [MinerU](https://github.com/opendatalab/MinerU)

Multi-threaded translation: [MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

Layout parsing: [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

## Star History

<a href="https://star-history.com/#Byaidu/PDFMathTranslate&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
 </picture>
</a>

<div align="center">

[English](README.md) | 简体中文

# PDFMathTranslate

<p>
  <!-- PyPI -->
  <a href="https://pypi.org/project/pdf2zh/">
    <img src="https://img.shields.io/pypi/v/pdf2zh"/></a>
  <a href="https://pepy.tech/projects/pdf2zh">
    <img src="https://static.pepy.tech/badge/pdf2zh"></a>
  <!-- License -->
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Byaidu/PDFMathTranslate"/></a>
  <a href="https://t.me/+Z9_SgnxmsmA5NzBl">
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=flat-squeare&logo=telegram&logoColor=white"/></a>
</p>

</div>

PDF 文档翻译及双语对照

- 📊 保留公式和图表

- 📄 保留可索引目录

- 🌐 支持多种翻译服务

欢迎在 [issues](https://github.com/Byaidu/PDFMathTranslate/issues) 或 [user group](https://t.me/+Z9_SgnxmsmA5NzBl) 中提供反馈

## 安装

要求 Python 版本 >=3.8, <=3.12

```bash
pip install pdf2zh
```

## 使用

命令行中执行翻译指令，在工作目录下生成翻译文档 `example-zh.pdf` 和双语对照文档 `example-dual.pdf`，默认使用 Google 作为翻译服务

有关如何设置环境变量，请参考 [ChatGPT](https://chatgpt.com/share/6734a83d-9d48-800e-8a46-f57ca6e8bcb4)

### 翻译完整文档

```bash
pdf2zh example.pdf
```

### 翻译部分文档

```bash
pdf2zh example.pdf -p 1-3,5
```

### 使用指定语言翻译

参考 [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages), [DeepL Languages Codes](https://developers.deepl.com/docs/resources/supported-languages)

```bash
pdf2zh example.pdf -li en -lo ja
```

### 使用 DeepL/DeepLX 翻译

参考 [DeepLX](https://github.com/OwO-Network/DeepLX)

设置环境变量构建接入点：`{DEEPL_SERVER_URL}/{DEEPL_AUTH_KEY}/translate`
- `DEEPL_SERVER_URL`（可选）, e.g., `export DEEPL_SERVER_URL=https://api.deepl.com`
- `DEEPL_AUTH_KEY`, e.g., `export DEEPL_AUTH_KEY=xxx`

```bash
pdf2zh example.pdf -s deepl
```

### 使用 Ollama 翻译

参考 [Ollama](https://github.com/ollama/ollama)

设置环境变量构建接入点：`{OLLAMA_HOST}/api/chat`
- `OLLAMA_HOST`（可选）, e.g., `export OLLAMA_HOST=https://localhost:11434`

```bash
pdf2zh example.pdf -s ollama:gemma2
```

### 使用 OpenAI/SiliconCloud/Zhipu 翻译

参考 [SiliconCloud](https://docs.siliconflow.cn/quickstart), [Zhipu](https://open.bigmodel.cn/dev/api/thirdparty-frame/openai-sdk)

设置环境变量构建接入点：`{OPENAI_BASE_URL}/chat/completions`
- `OPENAI_BASE_URL`（可选）, e.g., `export OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_API_KEY`, e.g., `export OPENAI_API_KEY=xxx`

```bash
pdf2zh example.pdf -s openai:gpt-4o
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

文档合并：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)

文档解析：[Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

文档提取：[MinerU](https://github.com/opendatalab/MinerU)

多线程翻译：[MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

布局解析：[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

文档标准：[PDF Explained](https://zxyle.github.io/PDF-Explained/), [PDF Cheat Sheets](https://pdfa.org/resource/pdf-cheat-sheets/)

## 贡献者

<a href="https://github.com/Byaidu/PDFMathTranslate/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Byaidu/PDFMathTranslate" />
</a>

## Star History

<a href="https://star-history.com/#Byaidu/PDFMathTranslate&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
 </picture>
</a>

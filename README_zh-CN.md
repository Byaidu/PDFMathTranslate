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

PDF 文档翻译及双语对照工具

- 📊 保留公式和图表

- 📄 保留可索引目录

- 🌐 支持多种翻译服务

欢迎在 [issues](https://github.com/Byaidu/PDFMathTranslate/issues) 或 [用户群](https://t.me/+Z9_SgnxmsmA5NzBl) 中提供反馈

## 安装

要求 Python 版本 >=3.8, <=3.12

```bash
pip install pdf2zh
```

## 使用

在命令行中执行翻译命令，生成译文文档 `example-zh.pdf` 和双语对照文档 `example-dual.pdf`，默认使用 Google 翻译服务

关于设置环境变量的详细说明，请参考 [ChatGPT](https://chatgpt.com/share/6734a83d-9d48-800e-8a46-f57ca6e8bcb4)

### 全文或部分文档翻译

- **全文翻译**

```bash
pdf2zh example.pdf
```

- **部分翻译**

```bash
pdf2zh example.pdf -p 1-3,5
```

### 指定源语言和目标语言

参考 [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages), [DeepL Languages Codes](https://developers.deepl.com/docs/resources/supported-languages)

```bash
pdf2zh example.pdf -li en -lo ja
```

### 使用不同的翻译服务

- **DeepL**

参考 [DeepL](https://support.deepl.com/hc/en-us/articles/360020695820-API-Key-for-DeepL-s-API)

设置环境变量构建接入点：`{DEEPL_SERVER_URL}/translate`
- `DEEPL_SERVER_URL`（可选）, e.g., `export DEEPL_SERVER_URL=https://api.deepl.com`
- `DEEPL_AUTH_KEY`, e.g., `export DEEPL_AUTH_KEY=xxx`

```bash
pdf2zh example.pdf -s deepl
```

- **DeepLX**

参考 [DeepLX](https://github.com/OwO-Network/DeepLX)

设置环境变量构建接入点：`{DEEPLX_SERVER_URL}/translate`
- `DEEPLX_SERVER_URL`（可选）, e.g., `export DEEPLX_SERVER_URL=https://api.deepl.com`
- `DEEPLX_AUTH_KEY`, e.g., `export DEEPLX_AUTH_KEY=xxx`

```bash
pdf2zh example.pdf -s deepl
```

- **Ollama**

参考 [Ollama](https://github.com/ollama/ollama)

设置环境变量构建接入点：`{OLLAMA_HOST}/api/chat`
- `OLLAMA_HOST`（可选）, e.g., `export OLLAMA_HOST=https://localhost:11434`

```bash
pdf2zh example.pdf -s ollama:gemma2
```

- **支持 OpenAI 协议的 LLM（如 OpenAI、SiliconCloud、Zhipu）**

参考 [SiliconCloud](https://docs.siliconflow.cn/quickstart), [Zhipu](https://open.bigmodel.cn/dev/api/thirdparty-frame/openai-sdk)

设置环境变量构建接入点：`{OPENAI_BASE_URL}/chat/completions`
- `OPENAI_BASE_URL`（可选）, e.g., `export OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_API_KEY`, e.g., `export OPENAI_API_KEY=xxx`

```bash
pdf2zh example.pdf -s openai:gpt-4o
```

- **Azure**

参考 [Azure Text Translation](https://docs.azure.cn/en-us/ai-services/translator/text-translation-overview)

需设置以下环境变量：
- `AZURE_APIKEY`, e.g., `export AZURE_APIKEY=xxx`
- `AZURE_ENDPOINT`, e.g., `export AZURE_ENDPOINT=https://api.translator.azure.cn/`
- `AZURE_REGION`, e.g., `export AZURE_REGION=chinaeast2`

```bash
pdf2zh example.pdf -s azure
```

### 指定例外规则

使用正则表达式指定需保留的公式字体与字符

```bash
pdf2zh example.pdf -f "(CM[^RT].*|MS.*|.*Ital)" -c "(\(|\||\)|\+|=|\d|[\u0080-\ufaff])"
```

### 图形化交互界面

<img src="./docs/images/before.png" width="500"/>

```bash
pdf2zh -i
```

详见 [GUI 文档](./docs/README_GUI.md)

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

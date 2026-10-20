<div align="center">

[English](../README.md) | 简体中文 | [繁體中文](README_zh-TW.md) | [日本語](README_ja-JP.md)

<img src="./images/banner.png" width="320px"  alt="PDF2ZH"/>  

<h2 id="title">PDFMathTranslate</h2>

<p>
  <!-- PyPI -->
  <a href="https://pypi.org/project/pdf2zh/">
    <img src="https://img.shields.io/pypi/v/pdf2zh"/></a>
  <a href="https://pepy.tech/projects/pdf2zh">
    <img src="https://static.pepy.tech/badge/pdf2zh"></a>
  <a href="https://hub.docker.com/repository/docker/byaidu/pdf2zh">
    <img src="https://img.shields.io/docker/pulls/byaidu/pdf2zh"></a>
  <!-- License -->
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Byaidu/PDFMathTranslate"/></a>
  <a href="https://huggingface.co/spaces/reycn/PDFMathTranslate-Docker">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97-Online%20Demo-FF9E0D"/></a>
  <a href="https://www.modelscope.cn/studios/AI-ModelScope/PDFMathTranslate">
    <img src="https://img.shields.io/badge/ModelScope-Demo-blue"></a>
  <a href="https://github.com/Byaidu/PDFMathTranslate/pulls">
    <img src="https://img.shields.io/badge/contributions-welcome-green"/></a>
  <a href="https://gitcode.com/Byaidu/PDFMathTranslate/overview">
    <img src="https://gitcode.com/Byaidu/PDFMathTranslate/star/badge.svg"></a>
  <a href="https://t.me/+Z9_SgnxmsmA5NzBl">
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=flat-squeare&logo=telegram&logoColor=white"/></a>
</p>

<a href="https://trendshift.io/repositories/12424" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12424" alt="Byaidu%2FPDFMathTranslate | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

科学 PDF 文档翻译工具，保留公式、图表、目录和注释。

本仓库是 PDFMathTranslate 生态的**统一接入口**：一个包同时提供命令行、Python API 和 MCP 服务，背后可以选用两个翻译核心。客户端和插件直接基于它开发，不需要再 fork。

<div align="center">
<img src="./images/preview.gif" width="80%"/>
</div>

<h2 id="choose">选择合适的工具</h2>

| 我想要… | 去这里 |
| --- | --- |
| 用桌面或手机应用阅读和翻译论文 | **[PDFMathReader](https://github.com/PDFMathTranslate/PDFMathReader)**：官方客户端，支持 macOS、Windows、Linux 和 [iOS](https://github.com/PDFMathTranslate/PDFMathReader-iOS) |
| 不装任何东西，在线或在浏览器里翻译 | **[沉浸式翻译 · BabelDOC](https://app.immersivetranslate.com/babel-doc/)**：每月有免费额度 |
| 在 Zotero 里翻译 | **[zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh)** |
| 让 AI 智能体（Claude、DeepSeek Harness 等）翻译 PDF | 本仓库的 **`pdf2zh --mcp`**，见 [MCP](#mcp) |
| 用命令行、在 Python 里调用，或者自己部署 | **本仓库**，继续往下看 |

<h3 id="ecosystem">各项目的关系</h3>

```
BabelDOC（排版引擎，funstory.ai）           pdf2zh v1 流程
                 \                          /
       babeldoc 核心（默认）          legacy 核心（可选）
                        \                /
      PDFMathTranslate：pdf2zh 命令行 · Python API · MCP   <- 本仓库
                 |                |                 |
          PDFMathReader     zotero-pdf2zh     AI 智能体 / dsh 插件
```

<h2 id="install">安装和使用</h2>

需要 Python 3.11 到 3.14；BabelDOC 核心需要 3.11 到 3.13。

```bash
pip install pdf2zh                # 命令行、Python API 和两个核心
pdf2zh document.pdf               # 生成 document-mono.pdf 和 document-dual.pdf
```

可选组件：

| 安装 | 增加的功能 |
| --- | --- |
| `pdf2zh[ultrafast]`、`pdf2zh[ocr]` | legacy 核心的[极速模式](./ADVANCED.md#ultrafast)和[自动 OCR](./ADVANCED.md#ocr) |
| `pdf2zh[mcp]` | MCP 服务（`pdf2zh --mcp`） |
| `pdf2zh[gui]` | Gradio 网页界面（`pdf2zh -i`） |
| `pdf2zh[backend]` | Flask/Celery HTTP 后端（[接口说明](./APIS.md#api-http)） |

带网页界面的 Docker 镜像：`docker run -d -p 7860:7860 byaidu/pdf2zh`，也可以从 [GitHub Container Registry](https://github.com/Byaidu/PDFMathTranslate/pkgs/container/pdfmathtranslate) 拉取。

<details>
<summary>下载模型时网络不通</summary>

两个核心第一次运行时都会从 Hugging Face 下载版面识别模型。如果所在地区下载失败，可以设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

其他问题请看[常见问题](https://github.com/Byaidu/PDFMathTranslate/wiki#-faq--%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98)。
</details>

<h3 id="kernels">翻译核心</h3>

| 核心 | 安装 | 适合 |
| --- | --- | --- |
| `legacy`（默认） | 已包含 | 原 pdf2zh v1 流程：更轻，支持 Python 3.14；支持极速模式、OCR 和自定义 ONNX 模型 |
| `babeldoc` | 已包含 | 版面还原度更高，由 [BabelDOC](https://github.com/funstory-ai/BabelDOC) 驱动；需要 Python 3.11 到 3.13 |

默认的 `--kernel auto` 使用 legacy，只有 legacy 不可用时才用 BabelDOC；要用 BabelDOC 请加 `--kernel babeldoc`。旧的 `--mode fast` / `--mode precise` 和 `--babeldoc` 仍然可用，分别等同于 `--kernel legacy` / `--kernel babeldoc`。

<h3 id="usage">命令行</h3>

```bash
pdf2zh paper.pdf -li en -lo ja -s deepl          # 指定源语言、目标语言和翻译服务
pdf2zh paper.pdf -s openai:gpt-4o-mini -p 1-3    # 服务:模型，只翻译部分页面
pdf2zh paper.pdf --kernel legacy --ultrafast     # legacy 核心的原生文本极速模式
pdf2zh --dir ./papers -o ./out                   # 批量翻译整个文件夹
```

| 参数 | 作用 |
| --- | --- |
| `files` | 本地文件或 URL |
| `-k`、`--kernel` | `auto`、`babeldoc` 或 `legacy` |
| `-li`、`-lo` | [源语言和目标语言](./ADVANCED.md#language) |
| `-s` | [翻译服务](./ADVANCED.md#services)，可写成 `服务:模型` |
| `-p` | [页码](./ADVANCED.md#partial)，如 `1,3-5` |
| `-o` | 输出目录 |
| `-t` | [线程数](./ADVANCED.md#threads) |
| `-f`、`-c` | [公式字体 / 字符正则](./ADVANCED.md#exceptions) |
| `--prompt` | [自定义提示词](./ADVANCED.md#prompt) |
| `--config` | [配置文件](./ADVANCED.md#cofig) |
| `--ignore-cache` | [跳过翻译缓存](./ADVANCED.md#cache) |
| `--ultrafast`、`--onnx`、`--skip-subset-fonts` | legacy 核心专用参数 |
| `-i`、`--flask`、`--celery` | 网页界面和 HTTP 后端（使用 legacy 核心） |
| `--mcp`、`--sse` | [MCP 服务](#mcp) |
| `--json` | 在 stdout 输出一行包含结果路径的 JSON，供以子进程方式调用 pdf2zh 的程序使用 |

完整说明见[高级用法](./ADVANCED.md)。

<h3 id="python">Python API</h3>

```python
from pdf2zh import TranslateRequest, get_kernel

kernel = get_kernel()                     # "auto"、"babeldoc" 或 "legacy"
request = TranslateRequest(files=["paper.pdf"], lang_in="en", lang_out="zh", service="google")
for result in kernel.translate(request):  # 或：await kernel.translate_async(request)
    print(result.mono_pdf, result.dual_pdf)
```

`pdf2zh.translate` 和 `pdf2zh.translate_stream` 继续保留，用于 legacy 核心，见[接口说明](./APIS.md)。

<h3 id="mcp">MCP</h3>

在任意 MCP 宿主里注册 pdf2zh。宿主会在需要时自己启动它，不用另外开着服务：

```json
{
  "mcpServers": {
    "pdf2zh": {
      "command": "uvx",
      "args": ["--from", "pdf2zh[mcp]", "pdf2zh", "--mcp"]
    }
  }
}
```

提供的工具：`translate_pdf(file, lang_in, lang_out, service, kernel, pages, output_dir)` 和 `list_kernels()`。详见 [MCP](./ADVANCED.md#mcp)。

<h3 id="examples">基于 pdf2zh 开发</h3>

[`examples/`](../examples/) 里有可直接运行的接入原型：带 REST 接口、实时进度和远程 MCP 的[网页前端与服务端](../examples/server/)，以及 [Claude](../examples/claude/)、[ChatGPT](../examples/chatgpt/)、[Zotero](../examples/zotero/) 和 [DeepSeek Harness](../examples/dsh/) 的接入方式。

<h2 id="updates">更新</h2>

- [2026 年 10 月] PDFMathTranslate 成为统一接入口：BabelDOC 作为默认核心在进程内运行，v1 流程改为可选的 `legacy` 核心；MCP 服务支持选择核心、翻译服务和页码；网页界面和 HTTP 后端改为可选安装；移除 `pdf2zh_next` 子模块。
- [2026 年 10 月 3 日] legacy 核心在相邻的中日韩文字和拉丁字母之间自动加空格。
- [2026 年 10 月 2 日] 新增 `--ultrafast` 原生文本极速模式（由 [@reycn](https://github.com/reycn) 提交）。
- [2026 年 9 月 8 日] 实验性 OCR，支持段落重组和自适应排版（由 [@reycn](https://github.com/reycn) 提交）。

<h2 id="acknowledgement">致谢</h2>

- [Immersive Translation](https://immersivetranslate.com) 为此项目的活跃贡献者提供每月的专业会员兑换码，详细信息请查看：[CONTRIBUTOR_REWARD.md](https://github.com/funstory-ai/BabelDOC/blob/main/docs/CONTRIBUTOR_REWARD.md)

- 文档合并：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)

- 文档解析：[Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

- 文档提取：[MinerU](https://github.com/opendatalab/MinerU)

- 文档预览：[Gradio PDF](https://github.com/freddyaboulton/gradio-pdf)

- 多线程翻译：[MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

- 布局解析：[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

- 文档标准：[PDF Explained](https://zxyle.github.io/PDF-Explained/)，[PDF Cheat Sheets](https://pdfa.org/resource/pdf-cheat-sheets/)

- 多语言字体：[Go Noto Universal](https://github.com/satbyy/go-noto-universal)

<h2 id="contrib">贡献者</h2>

<a href="https://github.com/Byaidu/PDFMathTranslate/graphs/contributors">
  <img src="https://opencollective.com/PDFMathTranslate/contributors.svg?width=890&button=false" />
</a>

![Alt](https://repobeats.axiom.co/api/embed/dfa7583da5332a11468d686fbd29b92320a6a869.svg "Repobeats analytics image")

<h2 id="star_hist">星标历史</h2>

<a href="https://star-history.com/#Byaidu/PDFMathTranslate&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
   <img alt="星标历史图表" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date"/>
 </picture>
</a>

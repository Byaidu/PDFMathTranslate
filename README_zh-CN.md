<div align="center">

[English](README.md) | 简体中文

<img src="./docs/images/banner.png" width="320px"  alt="PDF2ZH"/>  

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
  <a href="https://github.com/Byaidu/PDFMathTranslate/pulls">
    <img src="https://img.shields.io/badge/contributions-welcome-green"/></a>
  <a href="https://t.me/+Z9_SgnxmsmA5NzBl">
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=flat-squeare&logo=telegram&logoColor=white"/></a>
</p>

</div>

科学 PDF 文档翻译及双语对照工具

- 📊 保留公式、图表、目录和注释 *([预览效果](#preview))*
- 🌐 支持 [多种语言](#language) 和 [诸多翻译服务](#services)
- 🤖 提供 [命令行工具](#usage)，[图形交互界面](#gui)，以及 [容器化部署](#docker)

欢迎在 [GitHub Issues](https://github.com/Byaidu/PDFMathTranslate/issues)、[Telegram 用户群](https://t.me/+Z9_SgnxmsmA5NzBl) 或 [QQ 用户群](https://qm.qq.com/q/DixZCxQej0) 中提供反馈。

<h2 id="updates">近期更新</h2>

- [Nov. 26 2024] CLI 现在已支持（多个）在线 PDF 文件 *(by [@reycn](https://github.com/reycn))*  
- [Nov. 24 2024] 为降低依赖大小，提供 [ONNX](https://github.com/onnx/onnx) 支持 *(by [@Wybxc](https://github.com/Wybxc))*  
- [Nov. 23 2024] 🌟 [免费公共服务](#demo) 上线! *(by [@Byaidu](https://github.com/Byaidu))*  
- [Nov. 23 2024] 防止网页爬虫的防火墙 *(by [@Byaidu](https://github.com/Byaidu))*  
- [Nov. 22 2024] 图形用户界面现已支持意大利语，并获得了一些更新 *(by [@Byaidu](https://github.com/Byaidu), [@reycn](https://github.com/reycn))*  
- [Nov. 22 2024] 现在你可以将自己部署的服务分享给朋友了 *(by [@Zxis233](https://github.com/Zxis233))*  
- [Nov. 22 2024] 支持腾讯翻译 *(by [@hellofinch](https://github.com/hellofinch))*  
- [Nov. 21 2024] 图形用户界面现在支持下载双语文档 *(by [@reycn](https://github.com/reycn))*  
- [Nov. 20 2024] 🌟 提供了 [在线演示](#demo)！ *(by [@reycn](https://github.com/reycn))*  

<h2 id="preview">效果预览</h2>

<div align="center">
<img src="./docs/images/preview.gif" width="80%"/>
</div>

<h2 id="demo">在线演示 🌟</h2>

### 免费服务 (<https://pdf2zh.com/>)

你可以立即尝试 [免费公共服务](https://pdf2zh.com/) 而无需安装。

### Hugging Face 在线演示

你可以立即尝试 [在 HuggingFace 上的在线演示](https://huggingface.co/spaces/reycn/PDFMathTranslate-Docker) 而无需安装。
请注意，演示的计算资源有限，因此请避免滥用。

<h2 id="install">安装和使用</h2>

我们提供了三种使用该项目的方法：[命令行工具](#cmd)、[便携式安装](#portable)、[图形交互界面](#gui) 和 [容器化部署](#docker).

<h3 id="cmd">方法一、命令行工具</h3>

  1. 确保安装了版本大于 3.8 且小于 3.12 的 Python
  2. 安装此程序：

      ```bash
      pip install pdf2zh
      ```

  3. 执行翻译，生成文件位于 [当前工作目录](https://chatgpt.com/share/6745ed36-9acc-800e-8a90-59204bd13444)：

      ```bash
      pdf2zh document.pdf
      ```

<h3 id="portable">方法二、便携式安装</h3>

无需预先安装 Python 环境

下载并双击运行 [setup.bat](https://raw.githubusercontent.com/Byaidu/PDFMathTranslate/refs/heads/main/setup.bat)

<h3 id="gui">方法三、图形交互界面</h3>

1. 确保安装了版本大于 3.8 且小于 3.12 的 Python
2. 安装此程序：

      ```bash
      pip install pdf2zh
      ```

3. 开始在浏览器中使用：

      ```bash
      pdf2zh -i
      ```

4. 如果您的浏览器没有自动启动并跳转，请用浏览器打开：

    ```bash
    http://localhost:7860/
    ```

    <img src="./docs/images/gui.gif" width="500"/>

查看 [documentation for GUI](./docs/README_GUI.md) 获取细节说明

<h3 id="docker">方法四、容器化部署</h3>

1. 拉取 Docker 镜像并运行：

    ```bash
    docker pull byaidu/pdf2zh
    docker run -d -p 7860:7860 byaidu/pdf2zh
    ```

2. 通过浏览器打开：

    ```
    http://localhost:7860/
    ```

用于在云服务上部署容器镜像：

<a href="https://www.heroku.com/deploy?template=https://github.com/Byaidu/PDFMathTranslate">
  <img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy" height="26"></a>

<a href="https://render.com/deploy">
  <img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Koyeb" height="26"></a>

<a href="https://zeabur.com/templates/5FQIGX?referralCode=reycn">
  <img src="https://zeabur.com/button.svg" alt="Deploy on Zeabur" height="26"></a>

<a href="https://app.koyeb.com/deploy?type=git&builder=buildpack&repository=github.com/Byaidu/PDFMathTranslate&branch=main&name=pdf-math-translate">
  <img src="https://www.koyeb.com/static/images/deploy/button.svg" alt="Deploy to Koyeb" height="26"></a>

<h2 id="usage">高级选项</h2>

在命令行中执行翻译命令，在当前工作目录下生成译文文档 `example-zh.pdf` 和双语对照文档 `example-dual.pdf`，默认使用 Google 翻译服务

<img src="./docs/images/cmd.explained.png" width="580px"  alt="cmd"/>  

我们在下表中列出了所有高级选项，以供参考：

| Option    | Function | Example |
| -------- | ------- |------- |
| files | 本地文件 |  `pdf2zh ~/local.pdf` |
| links | 在线文件 |  `pdf2zh http://arxiv.org/paper.pdf` |
| `-i`  | [进入图形界面](#gui) |  `pdf2zh -i` |
| `-p`  | [仅翻译部分文档](#partial) |  `pdf2zh example.pdf -p 1` |
| `-li` | [源语言](#languages) |  `pdf2zh example.pdf -li en` |
| `-lo` | [目标语言](#languages) |  `pdf2zh example.pdf -lo zh` |
| `-s`  | [指定翻译服务](#services) |  `pdf2zh example.pdf -s deepl` |
| `-t`  | [多线程](#threads) | `pdf2zh example.pdf -t 1` |
| `-o`  | 输出目录 | `pdf2zh example.pdf -o output` |
| `-f`, `-c` | [例外规则](#exceptions) | `pdf2zh example.pdf -f "(MS.*)"` |

某些服务需要 [设置环境变量](https://chatgpt.com/share/6734a83d-9d48-800e-8a46-f57ca6e8bcb4)

<h3 id="partial">全文或部分文档翻译</h3>

- **全文翻译**

```bash
pdf2zh example.pdf
```

- **部分翻译**

```bash
pdf2zh example.pdf -p 1-3,5
```

<h3 id="language">指定源语言和目标语言</h3>

参考 [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages), [DeepL Languages Codes](https://developers.deepl.com/docs/resources/supported-languages)

```bash
pdf2zh example.pdf -li en -lo ja
```

<h3 id="services">使用不同的翻译服务</h3>

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

设置环境变量构建接入点：`{DEEPLX_SERVER_URL}/{DEEPLX_AUTH_KEY}/translate`

- `DEEPLX_SERVER_URL`（可选）, e.g., `export DEEPLX_SERVER_URL=https://api.deeplx.org`
- `DEEPLX_AUTH_KEY`, e.g., `export DEEPLX_AUTH_KEY=xxx`

```bash
pdf2zh example.pdf -s deeplx
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

- **腾讯机器翻译**

参考 [腾讯机器翻译](https://cloud.tencent.com/product/tmt)

需设置以下环境变量：

- `TENCENT_SECRET_ID`, e.g., `export TENCENT_SECRET_ID=AKIDxxx`
- `TENCENT_SECRET_KEY`, e.g., `export TENCENT_SECRET_KEY=xxx`

```bash
pdf2zh example.pdf -s tencent
```

<h3 id="exceptions">指定例外规则</h3>

使用正则表达式指定需保留的公式字体与字符：

```bash
pdf2zh example.pdf -f "(CM[^RT].*|MS.*|.*Ital)" -c "(\(|\||\)|\+|=|\d|[\u0080-\ufaff])"
```

<h3 id="threads">指定线程数量</h3>

使用 `-t` 指定翻译时使用的线程数量：

```bash
pdf2zh example.pdf -t 1
```

<h2 id="acknowledgement">致谢</h2>

- 文档合并：[PyMuPDF](https://github.com/pymupdf/PyMuPDF)

- 文档解析：[Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

- 文档提取：[MinerU](https://github.com/opendatalab/MinerU)

- 多线程翻译：[MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

- 布局解析：[DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

- 文档标准：[PDF Explained](https://zxyle.github.io/PDF-Explained/), [PDF Cheat Sheets](https://pdfa.org/resource/pdf-cheat-sheets/)

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
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date"/>
 </picture>
</a>

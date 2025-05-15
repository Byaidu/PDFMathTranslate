<div align="center">

<img src="./docs/images/banner.png" width="320px"  alt="PDF2ZH"/>

<h2 id="title">PDFMathTranslate</h2>

<p>
  <!-- PyPI -->
  <a href="https://pypi.org/project/pdf2zh/">
    <img src="https://img.shields.io/pypi/v/pdf2zh"></a>
  <a href="https://pepy.tech/projects/pdf2zh">
    <img src="https://static.pepy.tech/badge/pdf2zh"></a>
  <a href="https://hub.docker.com/repository/docker/byaidu/pdf2zh">
    <img src="https://img.shields.io/docker/pulls/byaidu/pdf2zh"></a>
  <a href="https://gitcode.com/Byaidu/PDFMathTranslate/overview">
    <img src="https://gitcode.com/Byaidu/PDFMathTranslate/star/badge.svg"></a>
  <a href="https://huggingface.co/spaces/reycn/PDFMathTranslate-Docker">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97-Online%20Demo-FF9E0D"></a>
  <a href="https://www.modelscope.cn/studios/AI-ModelScope/PDFMathTranslate">
    <img src="https://img.shields.io/badge/ModelScope-Demo-blue"></a>
  <a href="https://github.com/Byaidu/PDFMathTranslate/pulls">
    <img src="https://img.shields.io/badge/contributions-welcome-green"></a>
  <a href="https://t.me/+Z9_SgnxmsmA5NzBl">
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=flat-squeare&logo=telegram&logoColor=white"></a>
  <!-- License -->
  <a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Byaidu/PDFMathTranslate"></a>
</p>

<a href="https://trendshift.io/repositories/12424" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12424" alt="Byaidu%2FPDFMathTranslate | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

PDF scientific paper translation and bilingual comparison.

- 📊 Preserve formulas, charts, table of contents, and annotations _([preview](#preview))_.
- 🌐 Support [multiple languages](#language), and diverse [translation services](#services).
- 🤖 Provides [commandline tool](#usage), [interactive user interface](#gui), and [Docker](#docker)

Feel free to provide feedback in [GitHub Issues](https://github.com/Byaidu/PDFMathTranslate/issues) or [Telegram Group](https://t.me/+Z9_SgnxmsmA5NzBl).

For details on how to contribute, please consult the [Contribution Guide](https://github.com/Byaidu/PDFMathTranslate/wiki/Contribution-Guide---%E8%B4%A1%E7%8C%AE%E6%8C%87%E5%8D%97).

<h2 id="updates">Updates</h2>

- [Mar. 3, 2025] Experimental support for the new backend [BabelDOC](https://github.com/funstory-ai/BabelDOC) WebUI added as an experimental option (by [@awwaawwa](https://github.com/awwaawwa))
- [Feb. 22 2025] Better release CI and well-packaged windows-amd64 exe (by [@awwaawwa](https://github.com/awwaawwa))
- [Dec. 24 2024] The translator now supports local models on [Xinference](https://github.com/xorbitsai/inference) _(by [@imClumsyPanda](https://github.com/imClumsyPanda))_
- [Dec. 19 2024] Non-PDF/A documents are now supported using `-cp` _(by [@reycn](https://github.com/reycn))_
- [Dec. 13 2024] Additional support for backend by _(by [@YadominJinta](https://github.com/YadominJinta))_
- [Dec. 10 2024] The translator now supports OpenAI models on Azure _(by [@yidasanqian](https://github.com/yidasanqian))_

<h2 id="preview">Preview</h2>

<div align="center">
<img src="./docs/images/preview.gif" width="80%"/>
</div>

<h2 id="demo">Online Service 🌟</h2>

You can try our application out using either of the following demos:

- [Public free service](https://pdf2zh.com/) online without installation _(recommended)_.
- [Immersive Translate - BabelDOC](https://app.immersivetranslate.com/babel-doc/) 1000 free pages per month. _(recommended)_
- [Demo hosted on HuggingFace](https://huggingface.co/spaces/reycn/PDFMathTranslate-Docker)
- [Demo hosted on ModelScope](https://www.modelscope.cn/studios/AI-ModelScope/PDFMathTranslate) without installation.

Note that the computing resources of the demo are limited, so please avoid abusing them.

<h2 id="install">Installation and Usage</h2>

### Methods

For different use cases, we provide distinct methods to use our program:

<details open>
  <summary>1. UV install</summary>
</details>

<details>
  <summary>2. Windows exe</summary>
</details>

<details>
  <summary>3. Graphic user interface</summary>
</details>

<details>
  <summary>4. Docker</summary>
</details>

<details>
  <summary>5. Zotero Plugin</summary>
</details>

<details>
  <summary>6. Commandline</summary>
</details>

> [!TIP]
>
> - If you're using Windows and cannot open the file after downloading, please install [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) and try again.
>
> - If you cannot access Docker Hub, please try the image on [GitHub Container Registry](https://github.com/Byaidu/PDFMathTranslate/pkgs/container/pdfmathtranslate).
> ```bash
> docker pull ghcr.io/byaidu/pdfmathtranslate
> docker run -d -p 7860:7860 ghcr.io/byaidu/pdfmathtranslate
> ```

### Unable to install?

The present program needs an AI model(`wybxc/DocLayout-YOLO-DocStructBench-onnx`) before working and some users are not able to download due to network issues. If you have a problem with downloading this model, we provide a workaround using the following environment variable:

```shell
set HF_ENDPOINT=https://hf-mirror.com
```

For PowerShell user:

```shell
$env:HF_ENDPOINT = https://hf-mirror.com
```

If the solution does not work to you / you encountered other issues, please refer to [frequently asked questions](./docs/FAQ---常见问题.md).

<h2 id="usage">Advanced Options</h2>

Execute the translation command in the command line to generate the translated document `example-mono.pdf` and the bilingual document `example-dual.pdf` in the current working directory. Use Google as the default translation service. More support translation services can find [HERE](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#services).

<img src="./docs/images/cmd.explained.png" width="580px"  alt="cmd"/>

In the following table, we list all advanced options for reference:

| Option         | Function                                                                                                      | Example                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| files          | Local files                                                                                                   | `pdf2zh ~/local.pdf`                           |
| links          | Online files                                                                                                  | `pdf2zh http://arxiv.org/paper.pdf`            |
| `-i`           | [Enter GUI](#gui)                                                                                             | `pdf2zh -i`                                    |
| `-p`           | [Partial document translation](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#partial) | `pdf2zh example.pdf -p 1`                      |
| `-li`          | [Source language](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#languages)            | `pdf2zh example.pdf -li en`                    |
| `-lo`          | [Target language](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#languages)            | `pdf2zh example.pdf -lo zh`                    |
| `-s`           | [Translation service](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#services)         | `pdf2zh example.pdf -s deepl`                  |
| `-t`           | [Multi-threads](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#threads)                | `pdf2zh example.pdf -t 1`                      |
| `-o`           | Output dir                                                                                                    | `pdf2zh example.pdf -o output`                 |
| `-f`, `-c`     | [Exceptions](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#exceptions)                | `pdf2zh example.pdf -f "(MS.*)"`               |
| `-cp`          | Compatibility Mode                                                                                            | `pdf2zh example.pdf --compatible`              |
| `--skip-subset-fonts` | [Skip font subset](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#font-subset)  | `pdf2zh example.pdf --skip-subset-fonts`       |
| `--ignore-cache` | [Ignore translate cache](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#cache)       | `pdf2zh example.pdf --ignore-cache`            |
| `--share`      | Public link                                                                                                   | `pdf2zh -i --share`                            |
| `--authorized` | [Authorization](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#auth)                   | `pdf2zh -i --authorized users.txt [auth.html]` |
| `--prompt`     | [Custom Prompt](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#prompt)                 | `pdf2zh --prompt [prompt.txt]`                 |
| `--onnx`       | [Use Custom DocLayout-YOLO ONNX model]                                                                        | `pdf2zh --onnx [onnx/model/path]`              |
| `--serverport` | [Use Custom WebUI port]                                                                                       | `pdf2zh --serverport 7860`                     |
| `--dir`        | [batch translate]                                                                                             | `pdf2zh --dir /path/to/translate/`             |
| `--config`     | [configuration file](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#cofig)             | `pdf2zh --config /path/to/config/config.json`  |
| `--serverport` | [custom gradio server port]                                                                                   | `pdf2zh --serverport 7860`                     |
|`--babeldoc`| Use Experimental backend [BabelDOC](https://funstory-ai.github.io/BabelDOC/) to translate |`pdf2zh --babeldoc` -s openai example.pdf|

For detailed explanations, please refer to our document about [Advanced Usage](./docs/ADVANCED.md) for a full list of each option.

<h2 id="downstream">Secondary Development (APIs)</h2>

The current pdf2zh API is temporarily deprecated. The API will be provided again after [pdf2zh 2.0](https://github.com/Byaidu/PDFMathTranslate/issues/586) is released. For users who need programmatic access, please use the `babeldoc.high_level.async_translate` function of [BabelDOC](https://github.com/funstory-ai/BabelDOC).

This API being temporarily deprecated means: the relevant code will not be removed for now, but no technical support will be provided, and no bug fixes will be made.

> [!WARNING]
>
> pdf2zh 2.0 does not guarantee compatibility with versions prior to the v2.0.0 final release. Secondary development is not recommended. Please wait patiently for the API to stabilize.

<!-- For downstream applications, please refer to our document about [API Details](./docs/APIS.md) for futher information about:

- [Python API](./docs/APIS.md#api-python), how to use the program in other Python programs
- [HTTP API](./docs/APIS.md#api-http), how to communicate with a server with the program installed -->

<h2 id="langcode">Language Code</h2>

If you don't know what code to use to translate to the language you need, check out [this documentation](./docs/Language-Codes----语言代码.md)

<h2 id="todo">TODOs</h2>

- [ ] Parse layout with DocLayNet based models, [PaddleX](https://github.com/PaddlePaddle/PaddleX/blob/17cc27ac3842e7880ca4aad92358d3ef8555429a/paddlex/repo_apis/PaddleDetection_api/object_det/official_categories.py#L81), [PaperMage](https://github.com/allenai/papermage/blob/9cd4bb48cbedab45d0f7a455711438f1632abebe/README.md?plain=1#L102), [SAM2](https://github.com/facebookresearch/sam2)

- [ ] Fix page rotation, table of contents, format of lists

- [ ] Fix pixel formula in old papers

- [ ] Async retry except KeyboardInterrupt

- [ ] Knuth–Plass algorithm for western languages

- [ ] Support non-PDF/A files

- [ ] Plugins of [Zotero](https://github.com/zotero/zotero) and [Obsidian](https://github.com/obsidianmd/obsidian-releases)

<h2 id="acknowledgement">Acknowledgements</h2>

- [Immersive Translation](https://immersivetranslate.com) sponsors monthly Pro membership redemption codes for active contributors to this project, see details at: [CONTRIBUTOR_REWARD.md](https://github.com/funstory-ai/BabelDOC/blob/main/docs/CONTRIBUTOR_REWARD.md)

- New backend: [BabelDOC](https://github.com/funstory-ai/BabelDOC)

- Document merging: [PyMuPDF](https://github.com/pymupdf/PyMuPDF)

- Document parsing: [Pdfminer.six](https://github.com/pdfminer/pdfminer.six)

- Document extraction: [MinerU](https://github.com/opendatalab/MinerU)

- Document Preview: [Gradio PDF](https://github.com/freddyaboulton/gradio-pdf)

- Multi-threaded translation: [MathTranslate](https://github.com/SUSYUSTC/MathTranslate)

- Layout parsing: [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

- Document standard: [PDF Explained](https://zxyle.github.io/PDF-Explained/), [PDF Cheat Sheets](https://pdfa.org/resource/pdf-cheat-sheets/)

- Multilingual Font: [Go Noto Universal](https://github.com/satbyy/go-noto-universal)

- [Asynchronize](https://github.com/multimeric/Asynchronize/tree/master?tab=readme-ov-file)

- [Rich logging with multiprocessing](https://github.com/SebastianGrans/Rich-multiprocess-logging/tree/main)

<h2 id="conduct">Before submit your code</h2>

We welcome the active participation of contributors to make pdf2zh better. Before you are ready to submit your code, please refer to our [Code of Conduct](./docs/CODE_OF_CONDUCT.md) and [Contribution Guide](./docs/Contribution-Guide---贡献指南.md).

<h2 id="contrib">Contributors</h2>

<a href="https://github.com/Byaidu/PDFMathTranslate/graphs/contributors">
  <img src="https://opencollective.com/PDFMathTranslate/contributors.svg?width=890&button=false" />
</a>

![Alt](https://repobeats.axiom.co/api/embed/dfa7583da5332a11468d686fbd29b92320a6a869.svg "Repobeats analytics image")

<h2 id="star_hist">Star History</h2>

<a href="https://star-history.com/#Byaidu/PDFMathTranslate&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Byaidu/PDFMathTranslate&type=Date"/>
 </picture>
</a>

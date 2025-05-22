[**Advanced**](./introduction.md) > **Advanced** _(current)_

---

<h3 id="toc">Table of Contents</h3>

- [Command Line Args](#command-line-args)
- [Full / partial translation](#full--partial-translation)
- [Specify source and target languages](#specify-source-and-target-languages)
- [Translate wih exceptions](#translate-wih-exceptions)
<!-- - [Multi-threads](#threads) -->
- [Custom prompt](#custom-prompt)
<!-- - [Authorization](#auth) -->
- [Custom configuration](#custom-configuration)
<!-- - [Fonts Subseting](#fonts-subset) -->
- [Translation cache](#translation-cache)

---

<!-- <h3 id="cmd">Command Line Args</h3> -->
#### Command Line Args

Execute the translation command in the command line to generate the translated document `example-mono.pdf` and the bilingual document `example-dual.pdf` in the current working directory. Use Google as the default translation service. More support translation services can find [HERE](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#services).

<img src="./../images/cmd.explained.png" width="580px"  alt="cmd"/>

In the following table, we list all advanced options for reference:

##### Args

| Option                             | Function                                                                                         | Example                                                                                                                 |
|------------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| `files`                            | Local PDF file path                                                                              | `pdf2zh ~/local.pdf`                                                                                                    |
| `links`                            | Online files                                                                                     | `pdf2zh http://arxiv.org/paper.pdf`                                                                                     |
| `--output`                         | Output directory for files                                                                       | `pdf2zh example.pdf -o output`                                                                                          |
| `--<Services>`                     | Use [**specific service**](./Documentation-of-Translation-Services.md) for translation                                                             | `pdf2zh example.pdf --openai`<br>`pdf2zh example.pdf --deepseek`                                                        |
| `--help`, `-h`                     | Show help message and exit                                                                       | `pdf2zh -h`                                                                                                             |
| `--config-file`                    | Path to the configuration file                                                                   | `pdf2zh --config /path/to/config/config.json`                                                                           |
| `--report-interval`                | Progress report interval in seconds                                                              | `pdf2zh example.pdf --report-interval 5`                                                                                |
| `--debug`                          | Use debug logging level                                                                          | `pdf2zh -d`                                                                                                             |
| `--gui`                            | Interact with GUI                                                                                | `pdf2zh -i`                                                                                                             |
| `--warmup`                         | Only download and verify required assets then exit                                               | `pdf2zh example.pdf --warmup`                                                                                           |
| `--generate-offline-assets`        | Generate offline assets package in the specified directory                                       | `pdf2zh example.pdf --generate-offline-assets /path`                                                                    |
| `--restore-offline-assets`         | Restore offline assets package from the specified directory                                      | `pdf2zh example.pdf --restore-offline-assets /path`                                                                     |
| `--pages`                          | Partial document translation                                                                     | `pdf2zh example.pdf -p 1`                                                                                               |
| `--lang-in`                        | The code of source language                                                                      | `pdf2zh example.pdf -li en`                                                                                             |
| `--lang-out`                       | The code of target language                                                                      | `pdf2zh example.pdf -lo zh`                                                                                             |
| `--min-text-length`                | Minimum text length to translate                                                                 |                                                                                                                         |
| `--rpc-doclayout`                  | RPC service host address for document layout analysis                                            |                                                                                                                         |
| `--qps`                            | QPS limit for translation service                                                                | `pdf2zh example.pdf --qps 200`                                                                                          |
| `--ignore-cache`                   | Ignore translation cache                                                                         | `pdf2zh example.pdf --ignore-cache`                                                                                     |
| `--custom-system-prompt`           | Custom system prompt for translation. Used for `/no_think` in Qwen 3                             | `pdf2zh example.pdf --custom-system-prompt "/no_think You are a professional, authentic machine translation engine"`    |
| `--no-dual`                        | Do not output bilingual PDF files                                                                | `pdf2zh example.pdf --no-dual`                                                                                          |
| `--no-mono`                        | Do not output monolingual PDF files                                                              | `pdf2zh example.pdf --no-mono`                                                                                          |
| `--formular-font-pattern`          | Font pattern to identify formula text                                                            | `pdf2zh example.pdf --formular-font-pattern "(MS.*)"`                                                                   |
| `--formular-char-pattern`          | Character pattern to identify formula text                                                       | `pdf2zh example.pdf --formular-char-pattern "(MS.*)"`                                                                   |
| `--split-short-line`               | Force split short line into different paragraphs                                                 | `pdf2zh example.pdf --split-short-line`                                                                                 |
| `--short-line-split-factor`        | Split threshold factor for short lines                                                           |                                                                                                                         |
| `--skip-clean`                     | Skip PDF cleaning step                                                                           | `pdf2zh example.pdf --skip-clean`                                                                                       |
| `--dual-TRANSLATE-first`           | Put translated pages first in dual PDF mode                                                      | `pdf2zh example.pdf --dual-TRANSLATE-first`                                                                             |
| `--disable-rich-text-translate`    | Disable rich text translation                                                                    | `pdf2zh example.pdf --disable-rich-text-translate`                                                                      |
| `--enhance-compatibility`          | Enable all compatibility enhancement options                                                     | `pdf2zh example.pdf --enhance-compatibility`                                                                            |
| `--use-alternating-pages-dual`     | Use alternating pages mode for dual PDF                                                          | `pdf2zh example.pdf --use-alternating-pages-dual`                                                                       |
| `--watermark-output-mode`          | Watermark output mode for PDF files                                                              | `pdf2zh example.pdf --watermark-output-mode "NoWaterMark"`                                                              |
| `--max-pages-per-part`             | Maximum pages per part for split translation                                                     | `pdf2zh example.pdf --max-pages-per-part 1`                                                                             |
| `--translate-table-text`           | Translate table text (experimental)                                                              | `pdf2zh example.pdf --translate-table-text`                                                                             |
| `--skip-scanned-detection`         | Skip scanned detection                                                                           | `pdf2zh example.pdf --skip-scanned-detection`                                                                           |
| `--ocr-workaround`                 | Force translated text to be black and add white background                                       | `pdf2zh example.pdf --ocr-workaround`                                                                                   |

##### GUI Args

| Option                           | Function                                   | Example                                         |
|----------------------------------|--------------------------------------------|-------------------------------------------------|
| `--share`                        | Enable sharing mode                        | `pdf2zh --gui --share`                          |
| `--auth-file`                    | Path to the authentication file            | `pdf2zh --gui --auth-file /path`                |
| `--enabled-services`             | Enabled translation services               | `pdf2zh --gui --enabled-services "OpenAI"`      |
| `--disable-gui-sensitive-input`  | Disable GUI sensitive input                | `pdf2zh --gui --disable-gui-sensitive-input`    |
| `--disable-config-auto-save`     | Disable automatic configuration saving     | `pdf2zh --gui --disable-config-auto-save`       |

[⬆️ Back to top](#toc)

---

#### Full / partial translation

- Entire document

  ```bash
  pdf2zh example.pdf
  ```

- Part of the document

  ```bash
  pdf2zh example.pdf --part 1-3,5
  ```

[⬆️ Back to top](#toc)

---

#### Specify source and target languages

See [Google Languages Codes](https://developers.google.com/admin-sdk/directory/v1/languages), [DeepL Languages Codes](https://developers.deepl.com/docs/resources/supported-languages)

```bash
pdf2zh example.pdf --lang-in en -lang-out ja
```

[⬆️ Back to top](#toc)

---

#### Translate wih exceptions

Use regex to specify formula fonts and characters that need to be preserved:

```bash
pdf2zh example.pdf --formular-font-pattern "(CM[^RT].*|MS.*|.*Ital)" --formular-char-pattern "(\(|\||\)|\+|=|\d|[\u0080-\ufaff])"
```

Preserve `Latex`, `Mono`, `Code`, `Italic`, `Symbol` and `Math` fonts by default:

```bash
pdf2zh example.pdf --formular-font-pattern "(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Ital|.*Sym|.*Math)"
```

[⬆️ Back to top](#toc)

---

#### Custom prompt

<!-- Note: System prompt is currently not supported. See [this change](https://github.com/Byaidu/PDFMathTranslate/pull/637). -->

Custom system prompt for translation. It is mainly used to add the '/no_think' instruction of Qwen 3 in the pormpt.

```bash
pdf2zh example.pdf --custom-system-prompt "/no_think You are a professional, authentic machine translation engine"
```

Or write your system prompt in a .txt file and import it using the command below:

```bash
pdf2zh example.pdf --custom-system-prompt "prompt.txt"
```

For example:

```txt title="prompt.txt" linenums="1"
You are a professional, authentic machine translation engine. Only Output the translated text, do not include any other text.

Translate the following markdown source text to ${lang_out}. Keep the formula notation {v*} unchanged. Output translation directly without any additional text.

Source Text: ${text}

Translated Text:
```

In custom prompt file, there are three variables can be used.

| **Variable** | **Description**       |
|--------------|-----------------------|
| `lang_in`    | Input language        |
| `lang_out`   | Output language       |
| `text`       | Text to be translated |

[⬆️ Back to top](#toc)

---

#### Custom configuration

There are multiple ways to modify and import the configuration file.

!!! note "Configuration File Hierarchy"

    When modifying the same parameter using different methods, the software will apply changes according to the priority order below. 
    <br>
    Higher-ranked modifications will override lower-ranked ones.

    `cli/gui > env > user config > default config`

##### Modifying Configuration via Command Line Arguments

For most cases, you can directly pass your desired settings through command line arguments. Please refer to [Command Line Args](#cmd) for more information.

For example, if you want to enable a GUI window, you can use the following command:

```bash
pdf2zh --gui
```

#####　Modifying Configuration via Environment Variables

You can replace the `--` in command line arguments with `PDF2ZH_`, connect parameters using `=`, and replace `-` with `_` as environment variables.

For example, if you want to enable a GUI window, you can use the following command:

```bash
PDF2ZH_GUI=TRUE pdf2zh
```

#####　User-Specified Configuration File

You can specify a configuration file using the command line argument below:

```bash
pdf2zh --config-file '/path/config.toml'
```

If you are unsure about the config file format, please refer to the default configuration file described below.

#####　Default Configuration File

The default configuration file is located at `~/.config/pdf2zh`. Please do not modify the configuration files in the `default` directory. It is strongly recommended to refer to this configuration file's content and use method iii to implement your own configuration file.

[⬆️ Back to top](#toc)

---

#### Fonts subsetting

By default, PDFMathTranslate uses fonts subsetting to decrease sizes of output files. You can use `--skip-subset-fonts` option to disable fonts subsetting when encoutering compatibility issues.

```bash
pdf2zh example.pdf --skip-subset-fonts
```

[⬆️ Back to top](#toc)

---

#### Translation cache

PDFMathTranslate caches translated texts to increase speed and avoid unnecessary API calls for same contents. You can use `--ignore-cache` option to ignore translation cache and force retranslation.

```bash
pdf2zh example.pdf --ignore-cache
```

[⬆️ Back to top](#toc)

---

#### Deployment as a public services

PDFMathTranslate has added the features of **enabling partial services** and **hiding Backend information** in 
the configuration file. You can enable these by setting `ENABLED_SERVICES` and `HIDDEN_GRADIO_DETAILS` in the 
configuration file. Among them:

- `ENABLED_SERVICES` allows you to choose to enable only certain options, limiting the number of available services.
- `HIDDEN_GRADIO_DETAILS` will hide the real API_KEY on the web, preventing users from obtaining server-side keys.

A usable configuration is as follows:

```json
{
    "USE_MODELSCOPE": "0",
    "translators": [
        {
            "name": "grok",
            "envs": {
                "GORK_API_KEY": null,
                "GORK_MODEL": "grok-2-1212"
            }
        },
        {
            "name": "openai",
            "envs": {
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
                "OPENAI_API_KEY": "sk-xxxx",
                "OPENAI_MODEL": "gpt-4o-mini"
            }
        }
    ],
    "ENABLED_SERVICES": [
        "OpenAI",
        "Grok"
    ],
    "HIDDEN_GRADIO_DETAILS": true,
    "PDF2ZH_LANG_FROM": "English",
    "PDF2ZH_LANG_TO": "Simplified Chinese",
    "NOTO_FONT_PATH": "/app/SourceHanSerifCN-Regular.ttf"
}
```

[⬆️ Back to top](#toc)

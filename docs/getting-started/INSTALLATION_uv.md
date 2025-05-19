### Install PDFMathTranslate via uv

#### What is uv?

[uv](https://docs.astral.sh/uv/) is an extremely fast Python package and project manager, written in Rust.

#### Installation

1. Python installed (3.10 <= version <= 3.12);

2. Use the following command to use our package:

    ```bash
    pip install uv
    uv tool install --python 3.12 pdf2zh
    ```

After installation, please refer to [this page](./USAGE_commandline.md) to review the command line usage instructions.

### Use WebUI

After completing the step #2 of the installation mentioned above, enter this command in the terminal to open the WebUI:

```bash
pdf2zh -i
```
After about 30s to a minute enter this command, a webpage will open in your default browser. 
<br>
If it does not happen, you can try to manually access `http://localhost:7860/`.

!!! note

    If you encounter any issues during use WebUI, please refer to [this webpage](./USAGE_webui.md).
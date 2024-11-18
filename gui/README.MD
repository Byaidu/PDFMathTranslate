# GUI (early test version)

This subfolder provides the GUI mode of `pdf2zh`.

## Usage:
1. Make sure that the main tool and additional dependencies are installed. Extra modules required by the GUI are:

- GUI framework: `pip install gradio`
- PDF preview: `pip install pdf2image`
- PDF converter:
- - Mac `brew install poppler`
- - Other platforms: see [the link](https://pypi.org/project/pdf2image/) for details

2. Run
- `cd gui`
- `python main.py`

3. Drop the PDF file into the window and click `Translate`.

## Sample PDFs:

  <img src="./img/before.png" width="250" alt="Original">
  <img src="./img/after.png" width="250" alt="Translated">

## Maintainance
GUI maintained by [Rongxin](https://github.com/reycn)
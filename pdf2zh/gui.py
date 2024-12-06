import os
import shutil
from pathlib import Path
from pdf2zh import __version__
from pdf2zh.pdf2zh import extract_text
from pdf2zh.translator import (
    BaseTranslator,
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    OllamaTranslator,
    OpenAITranslator,
    ZhipuTranslator,
    SiliconTranslator,
    AzureTranslator,
    TencentTranslator,
)

import gradio as gr
import numpy as np
import pymupdf
import tqdm
import requests
import cgi

service_map: dict[str, BaseTranslator] = {
    "Google": GoogleTranslator,
    "Bing": BingTranslator,
    "DeepL": DeepLTranslator,
    "DeepLX": DeepLXTranslator,
    "Ollama": OllamaTranslator,
    "OpenAI": OpenAITranslator,
    "Zhipu": ZhipuTranslator,
    "Silicon": SiliconTranslator,
    "Azure": AzureTranslator,
    "Tencent": TencentTranslator,
}
lang_map = {
    "Chinese": "zh",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Japanese": "ja",
    "Korean": "ko",
    "Russian": "ru",
    "Spanish": "es",
    "Italian": "it",
}
page_map = {
    "All": None,
    "First": [0],
    "First 5 pages": list(range(0, 5)),
}

flag_demo = False
if os.getenv("PDF2ZH_DEMO"):
    flag_demo = True
    service_map = {
        "Google": GoogleTranslator,
    }
    page_map = {
        "First": [0],
        "First 20 pages": list(range(0, 20)),
    }
    client_key = os.getenv("PDF2ZH_CLIENT_KEY")
    server_key = os.getenv("PDF2ZH_SERVER_KEY")


def verify_recaptcha(response):
    recaptcha_url = "https://www.google.com/recaptcha/api/siteverify"
    print("reCAPTCHA", server_key, response)
    data = {"secret": server_key, "response": response}
    result = requests.post(recaptcha_url, data=data).json()
    print("reCAPTCHA", result.get("success"))
    return result.get("success")


def pdf_preview(file):
    doc = pymupdf.open(file)
    page = doc[0]
    pix = page.get_pixmap()
    image = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    return image


def upload_file(file, service, progress=gr.Progress()):
    preview_image = pdf_preview(file)
    return file, preview_image


def download_with_limit(url, save_path, size_limit):
    chunk_size = 1024
    total_size = 0
    with requests.get(url, stream=True, timeout=10) as response:
        response.raise_for_status()
        content = response.headers.get("Content-Disposition")
        try:  # filename from header
            _, params = cgi.parse_header(content)
            filename = params["filename"]
        except Exception:  # filename from url
            filename = os.path.basename(url)
        with open(save_path / filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                total_size += len(chunk)
                if size_limit and total_size > size_limit:
                    raise gr.Error("Exceeds file size limit")
                file.write(chunk)
    return save_path / filename


def translate(
    file_type,
    file_input,
    link_input,
    service,
    lang_from,
    lang_to,
    page_range,
    recaptcha_response,
    progress=gr.Progress(),
    *envs,
):
    """Translate PDF content using selected service."""
    if flag_demo and not verify_recaptcha(recaptcha_response):
        raise gr.Error("reCAPTCHA fail")

    progress(0, desc="Starting translation...")

    output = Path("pdf2zh_files")
    output.mkdir(parents=True, exist_ok=True)

    if file_type == "File":
        if not file_input:
            raise gr.Error("No input")
        file_path = shutil.copy(file_input, output)
    else:
        if not link_input:
            raise gr.Error("No input")
        file_path = download_with_limit(
            link_input,
            output,
            5 * 1024 * 1024 if flag_demo else None,
        )

    filename = os.path.splitext(os.path.basename(file_path))[0]
    file_en = output / f"{filename}.pdf"
    file_zh = output / f"{filename}-zh.pdf"
    file_dual = output / f"{filename}-dual.pdf"

    translator = service_map[service]
    selected_page = page_map[page_range]
    lang_from = lang_map[lang_from]
    lang_to = lang_map[lang_to]

    for i, env in enumerate(translator.envs.items()):
        os.environ[env[0]] = envs[i]

    print(f"Files before translation: {os.listdir(output)}")

    def progress_bar(t: tqdm.tqdm):
        progress(t.n / t.total, desc="Translating...")

    param = {
        "files": [file_en],
        "pages": selected_page,
        "lang_in": lang_from,
        "lang_out": lang_to,
        "service": f"{translator.name}",
        "output": output,
        "thread": 4,
        "callback": progress_bar,
    }
    print(param)
    extract_text(**param)
    print(f"Files after translation: {os.listdir(output)}")

    if not file_zh.exists() or not file_dual.exists():
        raise gr.Error("No output")

    try:
        translated_preview = pdf_preview(str(file_zh))
    except Exception:
        raise gr.Error("No preview")

    progress(1.0, desc="Translation complete!")

    return (
        str(file_zh),
        translated_preview,
        str(file_dual),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
    )


# Global setup
custom_blue = gr.themes.Color(
    c50="#E8F3FF",
    c100="#BEDAFF",
    c200="#94BFFF",
    c300="#6AA1FF",
    c400="#4080FF",
    c500="#165DFF",  # Primary color
    c600="#0E42D2",
    c700="#0A2BA6",
    c800="#061D79",
    c900="#03114D",
    c950="#020B33",
)

with gr.Blocks(
    title="PDFMathTranslate - PDF Translation with preserved formats",
    theme=gr.themes.Default(
        primary_hue=custom_blue, spacing_size="md", radius_size="lg"
    ),
    css="""
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}

    /* Add dashed border to input-file class */
    .input-file {
        border: 1.2px dashed #165DFF !important;
        border-radius: 6px !important;
        # background-color: #ffffff !important;
        transition: background-color 0.4s ease-out;
    }

    .input-file:hover {
        border: 1.2px dashed #165DFF !important;
        border-radius: 6px !important;
        color: #165DFF !important;
        background-color: #E8F3FF !important;
        transition: background-color 0.2s ease-in;
    }

    .progress-bar-wrap {
    border-radius: 8px !important;
    }
    .progress-bar {
    border-radius: 8px !important;
    }
    """,
    head=(
        """
    <script src="https://www.google.com/recaptcha/api.js?render=explicit" async defer></script>
    <script type="text/javascript">
        var onVerify = function(token) {
            el=document.getElementById('verify').getElementsByTagName('textarea')[0];
            el.value=token;
            el.dispatchEvent(new Event('input'));
        };
    </script>
    """
        if flag_demo
        else ""
    ),
) as demo:
    gr.Markdown(
        "# [PDFMathTranslate @ GitHub](https://github.com/Byaidu/PDFMathTranslate)"
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## File | < 5 MB" if flag_demo else "## File")
            file_type = gr.Radio(
                choices=["File", "Link"],
                label="Type",
                value="File",
            )
            file_input = gr.File(
                label="File",
                file_count="single",
                file_types=[".pdf"],
                type="filepath",
                elem_classes=["input-file"],
            )
            link_input = gr.Textbox(
                label="Link",
                visible=False,
                interactive=True,
            )
            gr.Markdown("## Option")
            service = gr.Dropdown(
                label="Service",
                choices=service_map.keys(),
                value="Google",
            )
            envs = []
            for i in range(3):
                envs.append(
                    gr.Textbox(
                        visible=False,
                        interactive=True,
                    )
                )
            with gr.Row():
                lang_from = gr.Dropdown(
                    label="Translate from",
                    choices=lang_map.keys(),
                    value="English",
                )
                lang_to = gr.Dropdown(
                    label="Translate to",
                    choices=lang_map.keys(),
                    value="Chinese",
                )
            page_range = gr.Radio(
                choices=page_map.keys(),
                label="Pages",
                value=list(page_map.keys())[0],
            )

            def on_select_service(service, evt: gr.EventData):
                translator = service_map[service]
                _envs = []
                for i in range(3):
                    _envs.append(gr.update(visible=False, value=""))
                for i, env in enumerate(translator.envs.items()):
                    _envs[i] = gr.update(
                        visible=True, label=env[0], value=os.getenv(env[0], env[1])
                    )
                return _envs

            def on_select_filetype(file_type):
                return (
                    gr.update(visible=file_type == "File"),
                    gr.update(visible=file_type == "Link"),
                )

            output_title = gr.Markdown("## Translated", visible=False)
            output_file = gr.File(label="Download Translation", visible=False)
            output_file_dual = gr.File(
                label="Download Translation (Dual)", visible=False
            )
            recaptcha_response = gr.Textbox(
                label="reCAPTCHA Response", elem_id="verify", visible=False
            )
            recaptcha_box = gr.HTML('<div id="recaptcha-box"></div>')
            translate_btn = gr.Button("Translate", variant="primary")
            tech_details_tog = gr.Markdown(
                f"""
                    <summary>Technical details</summary>
                    - GitHub: <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a><br>
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a><br>
                    - Version: {__version__}
                """,
                elem_classes=["secondary-text"],
            )
            service.select(
                on_select_service,
                service,
                envs,
            )
            file_type.select(
                on_select_filetype,
                file_type,
                [file_input, link_input],
                js=(
                    f"""
                    (a,b)=>{{
                        try{{
                            grecaptcha.render('recaptcha-box',{{
                                'sitekey':'{client_key}',
                                'callback':'onVerify'
                            }});
                        }}catch(error){{}}
                        return [a];
                    }}
                    """
                    if flag_demo
                    else ""
                ),
            )

        with gr.Column(scale=2):
            gr.Markdown("## Preview")
            preview = gr.Image(label="Document Preview", visible=True)

    # Event handlers
    file_input.upload(
        upload_file,
        inputs=[file_input, service],
        outputs=[file_input, preview],
        js=(
            f"""
            (a,b)=>{{
                try{{
                    grecaptcha.render('recaptcha-box',{{
                        'sitekey':'{client_key}',
                        'callback':'onVerify'
                    }});
                }}catch(error){{}}
                return [a];
            }}
            """
            if flag_demo
            else ""
        ),
    )

    translate_btn.click(
        translate,
        inputs=[
            file_type,
            file_input,
            link_input,
            service,
            lang_from,
            lang_to,
            page_range,
            recaptcha_response,
            *envs,
        ],
        outputs=[
            output_file,
            preview,
            output_file_dual,
            output_file,
            output_file_dual,
            output_title,
        ],
    ).then(lambda: None, js="()=>{grecaptcha.reset()}" if flag_demo else "")


def setup_gui(share=False):
    if flag_demo:
        demo.launch(server_name="0.0.0.0", max_file_size="5mb", inbrowser=True)
    else:
        try:
            demo.launch(server_name="0.0.0.0", debug=True, inbrowser=True, share=share)
        except Exception:
            print(
                "Error launching GUI using 0.0.0.0.\nThis may be caused by global mode of proxy software."
            )
            try:
                demo.launch(
                    server_name="127.0.0.1", debug=True, inbrowser=True, share=share
                )
            except Exception:
                print(
                    "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                )
                demo.launch(debug=True, inbrowser=True, share=True)


# For auto-reloading while developing
if __name__ == "__main__":
    setup_gui()

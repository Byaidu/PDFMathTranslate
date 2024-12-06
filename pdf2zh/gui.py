import os
import shutil
from pathlib import Path
from pdf2zh import __version__
from pdf2zh.pdf2zh import extract_text

import gradio as gr
import numpy as np
import pymupdf
import tqdm
import requests
import cgi

# Map service names to pdf2zh service options
# five value, padding with None
service_map = {
    "Google": (None, None, None),
    "DeepL": ("DEEPL_SERVER_URL", "DEEPL_AUTH_KEY", None),
    "DeepLX": ("DEEPLX_SERVER_URL", "DEEPLX_AUTH_KEY", None),
    "Ollama": ("OLLAMA_HOST", None, None),
    "OpenAI": ("OPENAI_BASE_URL", None, "OPENAI_API_KEY"),
    "Azure": ("AZURE_APIKEY", "AZURE_ENDPOINT", "AZURE_REGION"),
    "Tencent": ("TENCENT_SECRET_KEY", "TENCENT_SECRET_ID", None),
}
service_config = {
    "Google": {
        "apikey_content": {"visible": False},
        "apikey2_visibility": {"visible": False},
        "model_visibility": {"visible": False},
        "apikey3_visibility": {"visible": False},
    },
    "DeepL": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "apikey2_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[1]),
            "label": s[1],
        },
        "model_visibility": {"visible": False},
        "apikey3_visibility": {"visible": False},
    },
    "DeepLX": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "apikey2_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[1]),
            "label": s[1],
        },
        "model_visibility": {"visible": False},
        "apikey3_visibility": {"visible": False},
    },
    "Ollama": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "apikey2_visibility": {"visible": False},
        "model_visibility": lambda s: {"visible": True, "value": s[1]},
        "apikey3_visibility": {"visible": False},
    },
    "OpenAI": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[2]),
            "label": s[2],
        },
        "apikey2_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "model_visibility": {"visible": True, "value": "gpt-4o"},
        "apikey3_visibility": {"visible": False},
    },
    "Azure": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "apikey2_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[1]),
            "label": s[1],
        },
        "model_visibility": {"visible": False},
        "apikey3_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[2]),
            "label": s[2],
        },
    },
    "Tencent": {
        "apikey_content": lambda s: {
            "visible": True,
            "value": os.environ.get(s[0]),
            "label": s[0],
        },
        "apikey2_visibility": lambda s: {
            "visible": True,
            "value": os.environ.get(s[1]),
            "label": s[1],
        },
        "model_visibility": {"visible": False},
        "apikey3_visibility": {"visible": False},
    },
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
if os.environ.get("PDF2ZH_DEMO"):
    flag_demo = True
    service_map = {
        "Google": ("google", None, None),
    }
    page_map = {
        "First": [0],
        "First 20 pages": list(range(0, 20)),
    }
    client_key = os.environ.get("PDF2ZH_CLIENT_KEY")
    server_key = os.environ.get("PDF2ZH_SERVER_KEY")


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
    """Handle file upload, validation, and initial preview."""
    if not file or not os.path.exists(file):
        return None, None

    try:
        # Convert first page for preview
        preview_image = pdf_preview(file)

        return file, preview_image
    except Exception as e:
        print(f"Error converting PDF: {e}")
        return None, None


def download_with_limit(url, save_path, size_limit):
    chunk_size = 1024
    total_size = 0
    with requests.get(url, stream=True, timeout=10) as response:
        response.raise_for_status()
        content = response.headers.get("Content-Disposition")
        try:
            _, params = cgi.parse_header(content)
            filename = params["filename"]
        except Exception:
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
    apikey,
    apikey2,
    apikey3,
    model_id,
    lang_from,
    lang_to,
    page_range,
    recaptcha_response,
    progress=gr.Progress(),
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

    selected_service = service
    selected_page = page_map[page_range]
    lang_from = lang_map[lang_from]
    lang_to = lang_map[lang_to]

    VariablesSetter = TranslationVariables(service_map, apikey, apikey2, apikey3)
    VariablesSetter.process_service(lang_from, lang_to, selected_service)

    print(f"Files before translation: {os.listdir(output)}")

    def progress_bar(t: tqdm.tqdm):
        progress(t.n / t.total, desc="Translating...")

    param = {
        "files": [file_en],
        "pages": selected_page,
        "lang_in": lang_from,
        "lang_out": lang_to,
        "service": f"{selected_service}:{model_id}",
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


class TranslationVariables:
    def __init__(self, service_map, apikey, apikey2=None, apikey3=None):
        self.service_map = service_map
        self.apikey = apikey
        self.apikey2 = apikey2
        self.apikey3 = apikey3

    def set_language(self, lang_from, lang_to, selected_service):
        """Sets the language parameters based on the selected service."""
        if selected_service == "google":
            lang_from = "zh-CN" if lang_from == "zh" else lang_from
            lang_to = "zh-CN" if lang_to == "zh" else lang_to
        return lang_from, lang_to

    def set_environment_variables(self, selected_service):
        """Sets the environment variables based on the selected service."""
        print(self.service_map, selected_service)
        if selected_service in self.service_map:
            service_info = self.service_map[selected_service]
            if service_info[0]:
                os.environ.setdefault(service_info[0], self.apikey)
                print(service_info[0], self.apikey)
            if service_info[1]:
                os.environ.setdefault(service_info[1], self.apikey2)
                print(service_info[1], self.apikey2)
            if service_info[2]:
                os.environ.setdefault(service_info[2], self.apikey3)
                print(service_info[2], self.apikey3)
        else:
            raise gr.Error("Strange Service")

    def process_service(self, lang_from, lang_to, selected_service):
        """Main processing method for the selected service."""
        lang_from, lang_to = self.set_language(lang_from, lang_to, selected_service)
        self.set_environment_variables(selected_service)
        return lang_from, lang_to


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

    # .input-file label {
    #     color: #165DFF !important;
    #     border: 1.2px dashed #165DFF !important;
    #     border-left: none !important;
    #     border-top: none !important;
    # }
    # .input-file .wrap {
    #     color: #165DFF !important;
    # }
    # .input-file .or {
    #     color: #165DFF !important;
    # }
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
            with gr.Row():
                service = gr.Dropdown(
                    label="Service",
                    choices=service_map.keys(),
                    value="Google",
                )
                apikey = gr.Textbox(
                    label="API Key",
                    max_lines=1,
                    visible=False,
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
            model_id = gr.Textbox(
                label="Model ID",
                visible=False,
                interactive=True,
            )
            apikey2 = gr.Textbox(
                label="API Key 2",
                max_lines=1,
                visible=False,
            )
            apikey3 = gr.Textbox(
                label="API Key 3",
                max_lines=1,
                visible=False,
            )
            envs_status = "<span class='env-success'>- Properly configured.</span><br>"

            def details_wrapper(text_markdown):
                text = f"""
                    <summary>Technical details</summary>
                    {text_markdown}
                    - GitHub: <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a><br>
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a><br>
                    - Version: {__version__}
                """
                return text

            def env_var_checker(env_var_name: str) -> str:
                envvarflag = True
                envs_status = ""
                for envvar in env_var_name:
                    if envvar:
                        if not os.environ.get(envvar):
                            envs_status += f"<span class='env-warning'>- Warning: environmental not found or error ({envvar}).</span><br>"
                            envvarflag = False
                        else:
                            value = str(os.environ.get(envvar))
                            envs_status += (
                                f"- {envvar}: <code>{value[:13]}***</code><br>"
                            )

                if envvarflag:
                    envs_status = (
                        "<span class='env-success'>- Properly configured.</span><br>"
                    )
                else:
                    envs_status += "- Please make sure that the environment variables are properly configured "
                    envs_status += "(<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
                return details_wrapper(envs_status)

            def on_select_service(service, evt: gr.EventData):
                if service in service_config:
                    config = service_config[service]
                    apikey_content = gr.update(
                        **(
                            config["apikey_content"](service_map[service])
                            if callable(config["apikey_content"])
                            else config["apikey_content"]
                        )
                    )
                    apikey2_visibility = gr.update(
                        **(
                            config["apikey2_visibility"](service_map[service])
                            if callable(config["apikey2_visibility"])
                            else config["apikey2_visibility"]
                        )
                    )
                    model_visibility = gr.update(
                        **(
                            config["model_visibility"](service_map[service])
                            if callable(config["model_visibility"])
                            else config["model_visibility"]
                        )
                    )
                    apikey3_visibility = gr.update(
                        **(
                            config["apikey3_visibility"](service_map[service])
                            if callable(config["apikey3_visibility"])
                            else config["apikey3_visibility"]
                        )
                    )
                else:
                    raise gr.Error("Strange Service")
                return (
                    env_var_checker(service_map[service]),
                    model_visibility,
                    apikey_content,
                    apikey2_visibility,
                    apikey3_visibility,
                )

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
                details_wrapper(envs_status),
                elem_classes=["secondary-text"],
            )
            service.select(
                on_select_service,
                service,
                [tech_details_tog, model_id, apikey, apikey2, apikey3],
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
            apikey,
            apikey2,
            apikey3,
            model_id,
            lang_from,
            lang_to,
            page_range,
            recaptcha_response,
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

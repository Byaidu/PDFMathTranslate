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

# Map service names to pdf2zh service options
service_map = {
    "Google": "google",
    "DeepL": "deepl",
    "DeepLX": "deeplx",
    "Ollama": "ollama",
    "OpenAI": "openai",
    "Azure": "azure",
    "Tencent": "tencent",
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
        "Google": "google",
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


def translate(
    file_path,
    service,
    model_id,
    lang,
    page_range,
    recaptcha_response,
    progress=gr.Progress(),
):
    """Translate PDF content using selected service."""
    if not file_path:
        raise gr.Error("No input")

    if flag_demo and not verify_recaptcha(recaptcha_response):
        raise gr.Error("reCAPTCHA fail")

    progress(0, desc="Starting translation...")

    output = Path("pdf2zh_files")
    output.mkdir(parents=True, exist_ok=True)
    filename = os.path.splitext(os.path.basename(file_path))[0]
    file_en = output / f"{filename}.pdf"
    file_zh = output / f"{filename}-zh.pdf"
    file_dual = output / f"{filename}-dual.pdf"
    shutil.copyfile(file_path, file_en)

    selected_service = service_map.get(service, "google")
    selected_page = page_map.get(page_range, [0])
    lang_to = lang_map.get(lang, "zh")
    if selected_service == "google":
        lang_to = "zh-CN" if lang_to == "zh" else lang_to

    print(f"Files before translation: {os.listdir(output)}")

    def progress_bar(t: tqdm.tqdm):
        progress(t.n / t.total, desc="Translating...")

    param = {
        "files": [file_en],
        "pages": selected_page,
        "lang_in": "auto",
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
            file_input = gr.File(
                label="Document",
                file_count="single",
                file_types=[".pdf"],
                type="filepath",
                elem_classes=["input-file"],
            )
            gr.Markdown("## Option")
            service = gr.Dropdown(
                label="Service",
                info="Which translation service to use. Some require keys",
                choices=service_map.keys(),
                value="Google",
            )
            lang_to = gr.Dropdown(
                label="Translate to",
                info="Which language to translate to (optional)",
                choices=lang_map.keys(),
                value="Chinese",
            )
            page_range = gr.Radio(
                choices=page_map.keys(),
                label="Pages",
                info="Translate the full document or just few pages (optional)",
                value=list(page_map.keys())[0],
            )
            model_id = gr.Textbox(
                label="Model ID",
                info="Please enter the identifier of the model you wish to use (e.g., gemma2). "
                "This identifier will be used to specify the particular model for translation.",
                # value="gemma2",
                visible=False,  # hide by default
            )
            envs_status = "<span class='env-success'>- Properly configured.</span><br>"

            def details_wrapper(text_markdown):
                text = f"""
                <details>
                    <summary>Technical details</summary>
                    {text_markdown}
                    - GitHub: <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a><br>
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a><br>
                    - Version: {__version__}
                </details>"""
                return text

            def env_var_checker(env_var_name: str) -> str:
                if (
                    not os.environ.get(env_var_name)
                    or os.environ.get(env_var_name) == ""
                ):
                    envs_status = (
                        f"<span class='env-warning'>- Warning: environmental not found or error ({env_var_name})."
                        + "</span><br>- Please make sure that the environment variables are properly configured "
                        + "(<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
                    )
                else:
                    value = str(os.environ.get(env_var_name))
                    envs_status = (
                        "<span class='env-success'>- Properly configured.</span><br>"
                    )
                    if len(value) < 13:
                        envs_status += (
                            f"- Env: <code>{os.environ.get(env_var_name)}</code><br>"
                        )
                    else:
                        envs_status += f"- Env: <code>{value[:13]}***</code><br>"
                return details_wrapper(envs_status)

            def on_select_service(value, evt: gr.EventData):
                # hide model id by default
                model_visibility = gr.update(visible=False)
                # add a text description
                if value == "Google":
                    envs_status = details_wrapper(
                        "<span class='env-success'>- Properly configured.</span><br>"
                    )

                elif value == "DeepL":
                    envs_status = env_var_checker("DEEPL_AUTH_KEY")
                elif value == "DeepLX":
                    envs_status = env_var_checker("DEEPLX_AUTH_KEY")
                elif value == "Azure":
                    envs_status = env_var_checker("AZURE_APIKEY")
                elif value == "OpenAI":
                    model_visibility = gr.update(
                        visible=True, value="gpt-4o"
                    )  # show model id when service is selected
                    envs_status = env_var_checker("OPENAI_API_KEY")
                elif value == "Ollama":
                    model_visibility = gr.update(
                        visible=True, value="gemma2"
                    )  # show model id when service is selected
                    envs_status = env_var_checker("OLLAMA_HOST")
                else:
                    envs_status = (
                        "<span class='env-warning'>- Warning: model not in the list."
                        "</span><br>- Please report via "
                        "(<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
                    )
                return envs_status, model_visibility

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
            service.select(on_select_service, service, [tech_details_tog, model_id])

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
        inputs=[file_input, service, model_id, lang_to, page_range, recaptcha_response],
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

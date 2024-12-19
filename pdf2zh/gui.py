import asyncio
import cgi
import os
import shutil
import uuid
from asyncio import CancelledError
from pathlib import Path

import gradio as gr
import requests
import tqdm
from gradio_pdf import PDF

# from pdf2zh import __version__
from pdf2zh.high_level import translate
from pdf2zh.translator import (
    AnythingLLMTranslator,
    AzureOpenAITranslator,
    AzureTranslator,
    BaseTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    DifyTranslator,
    GeminiTranslator,
    GoogleTranslator,
    ModelScopeTranslator,
    OllamaTranslator,
    OpenAITranslator,
    SiliconTranslator,
    TencentTranslator,
    ZhipuTranslator,
)

# The following variables associate strings with translators
service_map: dict[str, BaseTranslator] = {
    "Google": GoogleTranslator,
    "Bing": BingTranslator,
    "DeepL": DeepLTranslator,
    "DeepLX": DeepLXTranslator,
    "Ollama": OllamaTranslator,
    "AzureOpenAI": AzureOpenAITranslator,
    "OpenAI": OpenAITranslator,
    "Zhipu": ZhipuTranslator,
    "ModelScope": ModelScopeTranslator,
    "Silicon": SiliconTranslator,
    "Gemini": GeminiTranslator,
    "Azure": AzureTranslator,
    "Tencent": TencentTranslator,
    "Dify": DifyTranslator,
    "AnythingLLM": AnythingLLMTranslator,
}

# The following variables associate strings with specific languages
lang_map = {
    "Simplified Chinese": "zh",
    "Traditional Chinese": "zh-TW",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Japanese": "ja",
    "Korean": "ko",
    "Russian": "ru",
    "Spanish": "es",
    "Italian": "it",
}

# The following variable associate strings with page ranges
page_map = {
    "All": None,
    "First": [0],
    "First 5 pages": list(range(0, 5)),
    "Others": None,
}

# Check if this is a public demo, which has resource limits
flag_demo = False

# Limit resources
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

# Check if everything unconfigured
if os.getenv("PDF2ZH_INIT") is not False:
    service_map = {
        "Google": GoogleTranslator,
    }


class EnvSync:
    """Two-way synchronization between a variable and its system environment counterpart."""

    def __init__(self, env_name: str, default_value: str = ""):
        self._name = env_name
        self._value = os.environ.get(env_name, default_value)
        # Initialize the environment variable if it doesn't exist
        if env_name not in os.environ:
            os.environ[env_name] = default_value

    @property
    def value(self) -> str:
        """Get the current value, ensuring sync with system env."""
        sys_value = os.environ.get(self._name)
        if sys_value != self._value:
            self._value = sys_value
        return self._value

    @value.setter
    def value(self, new_value: str):
        """Set the value and sync with system env."""
        self._value = new_value
        os.environ[self._name] = new_value

    def __str__(self) -> str:
        return self.value

    def __bool__(self) -> bool:
        return bool(self.value)


env_services = EnvSync("PDF2ZH_GUI_SERVICE")
env_lo = EnvSync("PDF2ZH_GUI_LO")
env_lo = EnvSync("PDF2ZH_GUI_LI")
env_deeplx_auth_key = EnvSync("DEEPLX_AUTH_KEY")
env_deeplx_server_url = EnvSync("DEEPLX_SERVER_URL")


# Public demo control
def verify_recaptcha(response):
    """
    This function verifies the reCAPTCHA response.
    """
    recaptcha_url = "https://www.google.com/recaptcha/api/siteverify"
    print("reCAPTCHA", server_key, response)
    data = {"secret": server_key, "response": response}
    result = requests.post(recaptcha_url, data=data).json()
    print("reCAPTCHA", result.get("success"))
    return result.get("success")


def download_with_limit(url: str, save_path: str, size_limit: int) -> str:
    """
    This function downloads a file from a URL and saves it to a specified path.

    Inputs:
        - url: The URL to download the file from
        - save_path: The path to save the file to
        - size_limit: The maximum size of the file to download

    Returns:
        - The path of the downloaded file
    """
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


def stop_translate_file(state: dict) -> None:
    """
    This function stops the translation process.

    Inputs:
        - state: The state of the translation process

    Returns:- None
    """
    session_id = state["session_id"]
    if session_id is None:
        return
    if session_id in cancellation_event_map:
        cancellation_event_map[session_id].set()


def translate_file(
    file_type,
    file_input,
    link_input,
    service,
    lang_from,
    lang_to,
    page_range,
    page_input,
    prompt,
    threads,
    recaptcha_response,
    state,
    progress=gr.Progress(),
    *envs,
):
    """
    This function translates a PDF file from one language to another.

    Inputs:
        - file_type: The type of file to translate
        - file_input: The file to translate
        - link_input: The link to the file to translate
        - service: The translation service to use
        - lang_from: The language to translate from
        - lang_to: The language to translate to
        - page_range: The range of pages to translate
        - page_input: The input for the page range
        - prompt: The custom prompt for the llm
        - threads: The number of threads to use
        - recaptcha_response: The reCAPTCHA response
        - state: The state of the translation process
        - progress: The progress bar
        - envs: The environment variables

    Returns:
        - The translated file
        - The translated file
        - The translated file
        - The progress bar
        - The progress bar
        - The progress bar
    """
    session_id = uuid.uuid4()
    state["session_id"] = session_id
    cancellation_event_map[session_id] = asyncio.Event()
    # Translate PDF content using selected service.
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
    file_raw = output / f"{filename}.pdf"
    file_mono = output / f"{filename}-mono.pdf"
    file_dual = output / f"{filename}-dual.pdf"

    translator = service_map[service]
    if page_range != "Others":
        selected_page = page_map[page_range]
    else:
        selected_page = []
        for p in page_input.split(","):
            if "-" in p:
                start, end = p.split("-")
                selected_page.extend(range(int(start) - 1, int(end)))
            else:
                selected_page.append(int(p) - 1)
    lang_from = lang_map[lang_from]
    lang_to = lang_map[lang_to]

    _envs = {}
    for i, env in enumerate(translator.envs.items()):
        _envs[env[0]] = envs[i]

    print(f"Files before translation: {os.listdir(output)}")

    def progress_bar(t: tqdm.tqdm):
        progress(t.n / t.total, desc="Translating...")

    try:
        threads = int(threads)
    except ValueError:
        threads = 1

    param = {
        "files": [str(file_raw)],
        "pages": selected_page,
        "lang_in": lang_from,
        "lang_out": lang_to,
        "service": f"{translator.name}",
        "output": output,
        "thread": int(threads),
        "callback": progress_bar,
        "cancellation_event": cancellation_event_map[session_id],
        "envs": _envs,
        "prompt": prompt,
    }
    try:
        translate(**param)
    except CancelledError:
        del cancellation_event_map[session_id]
        raise gr.Error("Translation cancelled")
    print(f"Files after translation: {os.listdir(output)}")

    if not file_mono.exists() or not file_dual.exists():
        raise gr.Error("No output")

    progress(1.0, desc="Translation complete!")

    return (
        str(file_mono),
        str(file_mono),
        str(file_dual),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=False),
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

custom_css = """
    body {
        -webkit-user-select: none; /* Safari */
        -ms-user-select: none; /* IE 10 and IE 11 */
        user-select: none; /* Standard syntax */}
        gradio-app {
        # background: 
        #     radial-gradient(farthest-side at -33.33% 50%,#0000 52%,#fcfcfc 54% 57%,#0000 59%) 0 calc(224px/2),
        #     radial-gradient(farthest-side at 50% 133.33%,#0000 52%,#fcfcfc 54% 57%,#0000 59%) calc(224px/2) 0,
        #     radial-gradient(farthest-side at 133.33% 50%,#0000 52%,#fcfcfc 54% 57%,#0000 59%),
        #     radial-gradient(farthest-side at 50% -33.33%,#0000 52%,#fcfcfc 54% 57%,#0000 59%),
        #     #ffffff !important;
        # background-size: calc(224px/4.667) 224px,224px calc(224px/4.667) !important;

        }
        # .secondary-text {
        color: #999 !important;
        }
        footer {
        visibility: hidden
        }
        .env-warning {
        color: #dd5500 !important;
        }
        .env-success {
        color: #559900 !important;
        }
        .logo {
        border: transparent;
        filter: saturate(0%);
        background-color:transparent !important;
        max-width: 4vh;
        margin-bottom: -1.2em;
        }
        .logo label {
        display: none;
        }
        .logo .top-panel {
        display: none;
        }
        .title {
        text-align: center;
        }
        .title h2 {
        color: #999999 !important;
        }
        .question {
        text-align: center;
        }
        .question h2 {
        color: #165DFF !important;
        }
        .info-text {
        text-align: center;
            margin-top: -5px;
        }
        .info-text p {
        color: #aaaaaa !important;
        }
        @keyframes pulse-background {
            0% {
                background-color: #FFFFFF;
        }
            25% {
                background-color: #FFFFFF;
        }
            50% {
                background-color: #E8F3FF;
        }
            75% {
                background-color: #FFFFFF;
        }
            100% {
                background-color: #FFFFFF;
        }
        }
        /* Add dashed border to input-file class */
        .input-file {
            border: 1.2px dashed #165DFF !important;
            border-radius: 6px !important;
            # background-color: #ffffff !important;
            animation: pulse-background 2s ease-in-out;
            transition: background-color 0.4s ease-out;
            width: 80vw;
            height: 50vh;
            margin: 0 auto;
        }
        .input-file:hover {
            border: 1.2px dashed #165DFF !important;
            border-radius: 6px !important;
            color: #165DFF !important;
            background-color: #E8F3FF !important;
            transition: background-color 0.2s ease-in;
            box-shadow: 4px 4px 20px rgba(22, 93, 255, 0.1);
        }
        .input-file label {
            color: #165DFF !important;
            border: 1.2px dashed #165DFF !important;
            border-left: none !important;
            border-top: none !important;
        }
        .input-file .top-panel {
            color: #165DFF !important;
            border: 1.2px dashed #165DFF !important;
            border-right: none !important;
            border-top: none !important;
        }
        .input-file .filename {
            color: #165DFF !important;
            background-color: #FFFFFF !important;
        }
        .input-file .download {
            color: #165DFF !important;
            background-color: #FFFFFF !important;
        }
        .input-file .wrap {
            color: #165DFF !important;
        }
        .input-file .or {
            color: #165DFF !important;
        }
        .progress-bar-wrap {
            border-radius: 8px !important;
        }
        .progress-bar {
            border-radius: 8px !important;
        }
        .options-row {
            align-items: center;
            display: flex;
            padding: 0 20vw 0 20vw !important;
        }
        .options-row .wrap {
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
            gap: 1rem;
        }
        .options-row .form label {
            color: #999;
        }
        .options-row .form {
            border: none !important;
            align-items: center !important;
        }
        .options-row [data-testid="block-info"] {
            display: none !important;
        }
        .logo-row {
            align-items: center;
        }
        .title-row {
            align-items: center;
        }
        .details-row {
            align-items: center;
        }
        .hide-frame {
            border: none !important;
        }
        .hide-frame .top-panel {
            display: none !important;
        }
        .hide-frame label {
            display: none !important;
        }
        .options-icon {
            height: 2em;
            width: 2em;
        }
        .preview-block .top-panel {
            display: none !important;
        }
        .preview-block {
            # width: 80vw !important;
            margin: 0 auto !important;
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
            padding-bottom: 0.8em !important;
            background-color: #ffffff !important;
            justify-content: center !important;
            align-items: center !important;
        }
        .preview-block .image-frame {
            width: 100% !important;
            # height: auto !important;
            object-fit: cover !important;
        }
        .preview-block .image-frame img {width: var(--size-full);
            object-fit: cover !important;
        }
        button .secondary {
            background-color: white !important;
        }
        .options-modal {
            position: absolute !important;
            # top: 20vh !important;
            left: 50vw !important;
            transform: translate(-25vw,-0vh) !important;
            z-index: 1000 !important;
            background: white !important;
            padding: 2rem !important;
            border-radius: 8px !important;
            box-shadow: 4px 4px 10px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.02) !important;
            width: 400px !important;
        }
        .options-modal .gr-group {
            background: white !important;
        }
        .options-modal .styler{
            background: white !important;
        }
        .options-modal h3 {
            margin-top: 0 !important;
            margin-bottom: 1.5rem !important;
            color: #333 !important;
        }
        .options-modal .form {
            margin-bottom: 1.5rem !important;
        }
        .options-modal .row {
            justify-content: flex-end !important;
            gap: 1rem !important;
        }
        .options-modal div button .secondary {
            background-color: white !important;
        }
        .options-modal button {
            min-width: 80px !important;
        }
        .options-btn {
            line-height: var(--line-md);
            background-color: #FFFFFF;
            border: 1.2px solid var(--checkbox-label-border-color) !important;
            border-radius: 6px !important;
            # color: var(--checkbox-label-border-color) !important;
            color: #999;
            font-weight: 500;
            font-size: var(--text-md);
            padding: 0.8em 1em 0.8em 1em !important;
            margin: 0.5em !important;
            transition: background-color 0.2s ease-in;
        }
        .options-btn:hover {
            background-color: #fafafa;
            # border: 1.2px solid #fcfcfc !important;
        }
        .form {
            background-color: rgba(0, 0, 0, 0) !important;
        }
        .first-page-checkbox {
            border: 1.2px solid var(--checkbox-label-border-color) !important;
            border-radius: 6px !important;
            font-weight: 500;
            padding: 0.8em 1em 0.8em 1em !important;
            background-color: #ffffff;
            !important;
            margin: 0.5em !important;
            align-items: center !important;
            font-size: var(--text-md);
            # color: var(--checkbox-label-border-color) !important;
            color: #999;
            transition: background-color 0.2s ease-in;
        }
        .first-page-checkbox label {
            align-items: center !important;
        }
        .first-page-checkbox:hover {
            border: 1.2px solid var(--checkbox-label-border-color) !important;
            color: #165DFF !important;
            background-color: #fafafa;
            !important;
            
    """

demo_recaptcha = """
    <script src="https://www.google.com/recaptcha/api.js?render=explicit" async defer></script>
    <script type="text/javascript">
        var onVerify = function(token) {
            el=document.getElementById('verify').getElementsByTagName('textarea')[0];
            el.value=token;
            el.dispatchEvent(new Event('input'));
        };
    </script>
    """

tech_details_string = """Opensourced at <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a> | GUI by <a href="https://github.com/reycn">Rongxin</a> | Version: Dev
                """
cancellation_event_map = {}


# The following code creates the GUI
# with gr.Blocks(
#     title="PDFMathTranslate - PDF Translation with preserved formats",
#     theme=gr.themes.Default(
#         primary_hue=custom_blue, spacing_size="md", radius_size="lg"
#     ),
#     css=custom_css,
#     head=demo_recaptcha if flag_demo else "",
# ) as demo:


def show_options():
    return gr.update(visible=True)


def save_options(api_key, api_url, model):
    # env_api_key.value = api_key
    # env_api_url.value = api_url
    # env_model.value = model
    return gr.update(visible=False)


def cancel_options():
    return gr.update(visible=False)


# First Tab: Local Document
with gr.Blocks() as tab_main:
    with gr.Row(elem_classes=["preview-row"]):
        preview = PDF(
            label="Translated",
            visible=False,
            height=1200,
            elem_classes=["preview-block"],
        )
    with gr.Row(elem_classes=["input-file-row"]):
        file_input = gr.File(
            label="Document",
            file_count="single",
            file_types=[".pdf"],
            interactive=True,
            elem_classes=["input-file", "secondary-text"],
            visible=True,
        )
        with gr.Row(visible=False) as hidden_inputs:
            input_type = gr.Textbox(value="File", label="Type")
            input_link = gr.Textbox(value="", label="Link")
            input_service = gr.Textbox(value="Google", label="Service")
            input_src_lang = gr.Textbox(value="English", label="Source Language")
            input_tgt_lang = gr.Textbox(
                value="Simplified Chinese", label="Target Language"
            )
            input_page_range = gr.Textbox(value="All", label="Page Range")
            input_pages = gr.Textbox(value="", label="Pages")
            input_prompt = gr.Textbox(value="", label="Prompt")
            input_threads = gr.Number(value=4, label="Threads")
            input_recaptcha = gr.Textbox(value="", label="Recaptcha")

    with gr.Row(elem_classes=["outputs-row"]):
        output_file_mono = gr.File(
            label="Translated", visible=False, elem_classes=["secondary-text"]
        )
        output_file_dual = gr.File(
            label="Translated (Bilingual)",
            visible=False,
            elem_classes=["secondary-text"],
        )

    file_input.upload(
        translate_file,
        inputs=[
            input_type,
            file_input,
            input_link,
            input_service,
            input_src_lang,
            input_tgt_lang,
            input_page_range,
            input_pages,
            input_prompt,
            input_threads,
            input_recaptcha,
            gr.State({}),
        ],
        outputs=[
            preview,
            output_file_mono,
            output_file_dual,
            preview,
            output_file_mono,
            output_file_dual,
            file_input,
        ],
    )

    # Event handlers
    def on_file_upload_immediate(file):
        if file:
            return [
                gr.update(visible=False),  # Hide first-page checkbox
                gr.update(visible=False),  # Hide options button
            ]
        return [gr.update(visible=True), gr.update(visible=True)]

    def on_file_upload_translate(file, first_page_only):
        option_first_page = "First" if first_page_only else "All"
        option_service = (
            service_map[gui_service.value] if gui_service.value else "Google"
        )
        if file:
            (output, output_dual, preview) = translate(
                file.name, option_service, "", "Chinese", option_first_page, ""
            )
            return [
                gr.update(visible=False),  # Hide file upload
                preview,  # Set preview image
                gr.update(visible=True),  # Show preview
                output,  # Set output file
                gr.update(visible=True),  # Set output file
                output_dual,  # Set output dual file
                gr.update(visible=True),  # Set output dual file
                gr.update(visible=False),  # Hide first-page checkbox
                gr.update(visible=False),  # Hide options button
                gr.update(visible=True),  # Show refresh button
            ]
        return [
            gr.update(visible=True),  # Show file upload
            None,  # Clear preview
            gr.update(visible=False),  # Hide preview
            None,  # Clear output file
            gr.update(visible=False),  # Hide output file
            None,  # Clear output dual file
            gr.update(visible=False),  # Hide output dual file
            gr.update(visible=True),  # Show first-page checkbox
            gr.update(visible=True),  # Show options button
            gr.update(visible=False),  # Hide refresh button
        ]


# Second Tab: Online Document
with gr.Blocks() as tab_url:
    link_input = gr.Textbox(
        label="Link", visible=True, interactive=True, elem_classes=["link-value"]
    )
    paste_btn = gr.Button("Paste from Clipboard", variant="secondary")
    translate_btn = gr.Button("Translate", variant="primary")

# Third Tab: Advanced Options
with gr.Blocks(visible=True, elem_classes=["options-modal"]) as tab_option:
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Translation")
            with gr.Group():
                gui_li = gr.Dropdown(
                    label="Source",
                    choices=["Chinese", "English"],
                    value=env_lo.value,
                    interactive=True,
                )
                gui_lo = gr.Dropdown(
                    label="Target",
                    choices=["Chinese", "English"],
                    value=env_lo.value,
                    interactive=True,
                )
            gr.Markdown("### Service")
            gui_service = gr.Dropdown(
                label="Provider",
                choices=list(service_map.keys()),
                value=env_services.value,
                interactive=True,
            )
            api_key_input = gr.Textbox(
                label="API Key",
                value=env_deeplx_auth_key.value,
                interactive=True,
            )
            api_url_input = gr.Textbox(
                label="Endpoint",
                value=env_deeplx_server_url.value,
                interactive=True,
                placeholder=" (optional) e.g., https://api.openaixxxx.com/v1",
            )
            gui_llm_prompt = gr.Textbox(
                label="Prompt",
                lines=2,
                max_lines=8,
                placeholder=" (optional) Customized prompt are only available for LLM-based translators.",
            )

        with gr.Column():
            gr.Markdown("### Document")
            gui_doc_type = gr.Radio(
                label="Output Type",
                choices=[
                    "Both",
                    "Mono-",
                    "Bi-lingual",
                ],
                value="Both",
            )
            gui_page_range = gr.Radio(
                label="Output Type",
                choices=["All", "First", "First 5 pages", "Others"],
                value="All",
            )
            gr.Markdown("### Technical")
            gui_exception = gr.Textbox(
                label="Rules for Exception",
                lines=2,
                max_lines=8,
                placeholder=" (optional) Texts matching the regex rule here will not be translated.",
            )
            gui_threads = gr.Slider(
                label="Multi-threads",
                minimum=1,
                maximum=32,
                step=1,
                interactive=True,
                value=1,
            )
            gui_compatile = gr.Checkbox(
                label="Improved compatibility",
            )
            gr.Markdown("""Version: Dev  
            [Need help? Report issues](https://github.com/Byaidu/PDFMathTranslate/issues)""")
    # Connect the options events
    # more_options.click(show_options, outputs=[options_modal])

    # cancel_btn.click(cancel_options, outputs=[options_modal])

    # save_btn.click(
    #     save_options,
    #     inputs=[api_key_input, api_url_input, model_input],
    #     outputs=[options_modal],
    # )

# Main Interface
with gr.Blocks(
    title="PDFMathTranslate - PDF Translation with preserved formats",
    theme=gr.themes.Default(
        primary_hue=custom_blue, spacing_size="md", radius_size="lg"
    ),
    css=custom_css,
    head=demo_recaptcha if flag_demo else "",
) as demo:
    with gr.Row(elem_classes=["logo-row"]):
        gr.Image("./docs/images/banner.png", elem_classes=["logo"])
    with gr.Row(elem_classes=["title-row"]):
        gr.Markdown(
            "## PDFMathTranslate",
            elem_classes=["title"],
        )
    gr.TabbedInterface(
        [tab_main, tab_url, tab_option],
        ["Local Document", "Online Document", "Advanced Options"],
    )
    gr.Markdown(tech_details_string, elem_classes=["secondary-text"])


# state = gr.State({"session_id": None})

# translate_btn.click(
#     translate_file,
#     inputs=[
#         file_type,
#         file_input,
#         link_input,
#         service,
#         lang_from,
#         lang_to,
#         page_range,
#         page_input,
#         prompt,
#         threads,
#         recaptcha_response,
#         state,
#         *envs,
#     ],
#     outputs=[
#         output_file_mono,
#         preview,
#         output_file_dual,
#         output_file_mono,
#         output_file_dual,
#         output_title,
#     ],
# ).then(lambda: None, js="()=>{grecaptcha.reset()}" if flag_demo else "")

# cancellation_btn.click(
#     stop_translate_file,
#     inputs=[state],
# )


def parse_user_passwd(file_path: str) -> tuple:
    """
    Parse the user name and password from the file.

    Inputs:
        - file_path: The file path to read.
    Outputs:
        - tuple_list: The list of tuples of user name and password.
        - content: The content of the file
    """
    tuple_list = []
    content = ""
    if not file_path:
        return tuple_list, content
    if len(file_path) == 2:
        try:
            with open(file_path[1], "r", encoding="utf-8") as file:
                content = file.read()
        except FileNotFoundError:
            print(f"Error: File '{file_path[1]}' not found.")
    try:
        with open(file_path[0], "r", encoding="utf-8") as file:
            tuple_list = [
                tuple(line.strip().split(",")) for line in file if line.strip()
            ]
    except FileNotFoundError:
        print(f"Error: File '{file_path[0]}' not found.")
    return tuple_list, content

    # Connect the options events
    # more_options.click(show_options, outputs=[options_modal])

    # cancel_btn.click(cancel_options, outputs=[options_modal])

    # save_btn.click(
    #     save_options,
    #     inputs=[api_key_input, api_url_input, model_input],
    #     outputs=[options_modal],
    # )


def setup_gui(share: bool = False, auth_file: list = ["", ""]) -> None:
    """
    Setup the GUI with the given parameters.

    Inputs:
        - share: Whether to share the GUI.
        - auth_file: The file path to read the user name and password.

    Outputs:
        - None
    """
    user_list, html = parse_user_passwd(auth_file)
    if flag_demo:
        demo.launch(server_name="0.0.0.0", max_file_size="5mb", inbrowser=True)
    else:
        if len(user_list) == 0:
            try:
                demo.launch(
                    server_name="0.0.0.0", debug=True, inbrowser=True, share=share
                )
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
        else:
            try:
                demo.launch(
                    server_name="0.0.0.0",
                    debug=True,
                    inbrowser=True,
                    share=share,
                    auth=user_list,
                    auth_message=html,
                    reload=True,
                )
            except Exception:
                print(
                    "Error launching GUI using 0.0.0.0.\nThis may be caused by global mode of proxy software."
                )
                try:
                    demo.launch(
                        server_name="127.0.0.1",
                        debug=True,
                        inbrowser=True,
                        share=share,
                        auth=user_list,
                        auth_message=html,
                    )
                except Exception:
                    print(
                        "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                    )
                    demo.launch(
                        debug=True,
                        inbrowser=True,
                        share=True,
                        auth=user_list,
                        auth_message=html,
                    )


# For auto-reloading while developing
if __name__ == "__main__":
    setup_gui()

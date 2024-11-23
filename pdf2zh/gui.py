import os
import re
import subprocess

import gradio as gr
import numpy as np
import pymupdf

# Map service names to pdf2zh service options
service_map = {
    "Google": "google",
    "DeepL": "deepl",
    "DeepLX": "deeplx",
    "Ollama": "ollama",
    "OpenAI": "openai",
    "Azure": "azure",
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
}


def pdf_preview(file):
    doc = pymupdf.open(file)
    page = doc[0]
    pix = page.get_pixmap()
    # Get only the top half of the image
    height = pix.height
    half_height = height // 2
    image = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    image = image[:half_height, :, :]  # Take only the top half
    return image


def upload_file(file, service, progress=gr.Progress()):
    """Handle file upload, validation, and initial preview."""
    if not file or not os.path.exists(file):
        return None, None, gr.update(visible=False)

    progress(0.3, desc="Converting PDF for preview...")
    try:
        # Convert first page for preview
        preview_image = pdf_preview(file)

        return file, preview_image, gr.update(visible=True)
    except Exception as e:
        print(f"Error converting PDF: {e}")
        return None, None, gr.update(visible=False)


def translate(
    file_path, service, model_id, lang, page_range, extra_args, progress=gr.Progress()
):
    """Translate PDF content using selected service."""
    if not file_path:
        return (
            None,
            None,
            None,
        )

    progress(0, desc="Starting translation...")

    # Create a temporary working directory using Gradio's file utilities
    temp_path = "./gradio_files"
    if os.path.exists(temp_path):
        for f in os.listdir(temp_path):
            os.remove(os.path.join(temp_path, f))
    else:
        os.mkdir(temp_path)
    file_original = f"{temp_path}/input.pdf"

    # Copy input file to temp directory
    progress(0.05, desc="Preparing files...")
    with open(file_path, "rb") as src, open(file_original, "wb") as dst:
        dst.write(src.read())

    selected_service = service_map.get(service, "google")
    lang_to = lang_map.get(lang, "zh")

    # Execute translation in temp directory with real-time progress
    progress(0.08, desc="Loading AI models...")

    # Prepare extra arguments
    extra_args = extra_args.strip()
    # Add page range arguments
    if page_range == "All":
        extra_args += ""
    elif page_range == "First":
        extra_args += " -p 1"
    elif page_range == "First 5 pages":
        extra_args += " -p 1-5"

    # Execute translation command
    if selected_service == "google":
        lang_to = "zh-CN" if lang_to == "zh" else lang_to

    if selected_service in ["ollama", "openai"]:
        command = f'cd "{temp_path}" && pdf2zh input.pdf -lo {lang_to} -s {selected_service}:{model_id} {extra_args}'
    else:
        command = f'cd "{temp_path}" && pdf2zh input.pdf -lo {lang_to} -s {selected_service} {extra_args}'
    progress(0.12, desc="Loading AI models...")
    print(f"Executing command: {command}")
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    # Monitor progress from command output
    while True:
        output = process.stdout.readline()
        if output == "" and process.poll() is not None:
            progress(0.2, desc="Waiting for model response...")
            break
        if output:
            print(f"Command output: {output.strip()}")
            # Look for percentage in output
            match = re.search(r"(\d+)%", output.strip())
            if match:
                progress(0.3, desc=f"Starting translation with {selected_service}...")
                percent = int(match.group(1))
                # Map command progress (0-100%) to our progress range (30-80%)
                progress_val = 0.3 + (percent * 0.5 / 100)
                progress(
                    progress_val,
                    desc=f"Translating content using {selected_service}. {percent}% pages translated / overall ",
                )

    # Get the return code
    return_code = process.poll()
    print(f"Command completed with return code: {return_code}")

    # Copy the translated files to permanent locations
    progress(0.89, desc="Checking results...")
    # Check if translation was successful
    final_path = "./gradio_files/input-zh.pdf"
    final_path_dual = "./gradio_files/input-dual.pdf"

    # Copy the translated files to permanent locations
    progress(0.9, desc="Saving translated files...")
    if not os.path.exists(final_path) and not os.path.exists(final_path_dual):
        print("Translation failed: No output files found")
        return (
            None,
            None,
            None,
        )

    # Generate preview of translated PDF
    progress(0.98, desc="Generating preview...")
    try:
        preview = pdf_preview(str(final_path))
    except Exception as e:
        print(f"Error generating preview: {e}")
        preview = None

    progress(1.0, desc="Translation complete!")
    return (str(final_path), str(final_path_dual), preview)


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
env_deeplx_auth_key = EnvSync("DEEPLX_AUTH_KEY")
env_deeplx_server_url = EnvSync("DEEPLX_SERVER_URL")


# Global setup
with gr.Blocks(
    title="PDFMathTranslate - PDF Translation with preserved formats",
    theme=gr.themes.Default(
        primary_hue=custom_blue, spacing_size="md", radius_size="lg"
    ),
    css="""
    body {
        -webkit-user-select: none; /* Safari */
        -ms-user-select: none; /* IE 10 and IE 11 */
        user-select: none; /* Standard syntax */}
        gradio-app {
        background: 
            radial-gradient(farthest-side at -33.33% 50%,#0000 52%,#fcfcfc 54% 57%,#0000 59%) 0 calc(224px/2),
            radial-gradient(farthest-side at 50% 133.33%,#0000 52%,#fcfcfc 54% 57%,#0000 59%) calc(224px/2) 0,
            radial-gradient(farthest-side at 133.33% 50%,#0000 52%,#fcfcfc 54% 57%,#0000 59%),
            radial-gradient(farthest-side at 50% -33.33%,#0000 52%,#fcfcfc 54% 57%,#0000 59%),
            #ffffff !important;
        background-size: calc(224px/4.667) 224px,224px calc(224px/4.667) !important;

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
            justify-content: center !important;
            align-items: center !important;
            background-color: #eeeeee !important;
        }
        .preview-block .image-frame {
            width: 100% !important;
            # height: auto !important;
            object-fit: cover !important;
        }
        .preview-block .image-frame img {width: var(--size-full);
            object-fit: cover !important;
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
            
    """,
) as demo:
    with gr.Row(elem_classes=["logo-row"]):
        gr.Image("./docs/images/banner.png", elem_classes=["logo"])
    with gr.Row(elem_classes=["title-row"]):
        gr.Markdown("## PDFMathTranslate", elem_classes=["title"])
    with gr.Row(elem_classes=["input-file-row"]):
        file_input = gr.File(
            label="Document",
            file_count="single",
            file_types=[".pdf"],
            interactive=True,
            elem_classes=["input-file", "secondary-text"],
            visible=True,
        )
        preview = gr.Image(
            label="Preview", visible=False, elem_classes=["preview-block"]
        )
    with gr.Row(elem_classes=["outputs-row"]):
        output_file = gr.File(
            label="Translated", visible=False, elem_classes=["secondary-text"]
        )
        output_file_dual = gr.File(
            label="Translated (Bilingual)",
            visible=False,
            elem_classes=["secondary-text"],
        )
    with gr.Row(elem_classes=["options-row"]):
        first_page_only = gr.Checkbox(
            label="Only first page",
            value=False,
            interactive=True,
            elem_classes=["first-page-checkbox", "secondary-text"],
        )
        more_options = gr.Button(
            "More options",
            variant="secondary",
            elem_classes=["options-btn"],
        )
    with gr.Row(elem_classes=["options-row"]):
        refresh = gr.Button(
            "Translate another PDF",
            variant="primary",
            elem_classes=["refresh-btn"],
            visible=False,
        )

    def show_options():
        return gr.update(visible=True)

    def save_options(api_key, api_url, model):
        env_api_key.value = api_key
        env_api_url.value = api_url
        env_model.value = model
        return gr.update(visible=False)

    def cancel_options():
        return gr.update(visible=False)

    # Options modal
    with gr.Column(visible=False, elem_classes=["options-modal"]) as options_modal:
        gr.Markdown("## Advanced Options")
        with gr.Group():
            gui_service = gr.Dropdown(
                label="Translation Service",
                choices=list(service_map.keys()),
                value=env_services.value,
                interactive=True,
            )
            api_key_input = gr.Textbox(
                label="DeepLX Auth Key (required)",
                value=env_deeplx_auth_key.value,
                interactive=True,
            )
            api_url_input = gr.Textbox(
                label="DeepLX ServerURL (optional)",
                value=env_deeplx_server_url.value,
                interactive=True,
            )
            gui_lo = gr.Dropdown(
                label="Target Language",
                choices=["Chinese", "English"],
                value=env_lo.value,
                interactive=True,
            )
            with gr.Row():
                cancel_btn = gr.Button("Cancel")
                save_btn = gr.Button("Save", variant="primary")

    # Connect the options events
    more_options.click(show_options, outputs=[options_modal])

    cancel_btn.click(cancel_options, outputs=[options_modal])

    save_btn.click(
        save_options,
        inputs=[api_key_input, api_url_input, model_input],
        outputs=[options_modal],
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
        option_service = service_map[gui_service] if gui_service else "Google"
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

    file_input.upload(
        fn=on_file_upload_immediate,
        inputs=[file_input],
        outputs=[first_page_only, more_options],
    ).then(
        fn=on_file_upload_translate,
        inputs=[file_input, first_page_only],
        outputs=[
            file_input,
            preview,
            preview,
            output_file,
            output_file,
            output_file_dual,
            output_file_dual,
            first_page_only,
            more_options,
            refresh,
        ],
    )

    def on_refresh_click():
        return [
            gr.update(value=None, visible=True),  # Clear file input
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

    refresh.click(
        on_refresh_click,
        outputs=[
            file_input,
            preview,
            preview,
            output_file,
            output_file,
            output_file_dual,
            output_file_dual,
            first_page_only,
            more_options,
            refresh,
        ],
    )


def setup_gui():
    try:
        demo.launch(server_name="0.0.0.0", debug=True, inbrowser=True, share=False)
    except Exception:
        print(
            "Error launching GUI using 0.0.0.0.\nThis may be caused by global mode of proxy software."
        )
        try:
            demo.launch(
                server_name="127.0.0.1", debug=True, inbrowser=True, share=False
            )
        except Exception:
            print(
                "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
            )
            demo.launch(server_name="0.0.0.0", debug=True, inbrowser=True, share=True)


# For auto-reloading while developing
if __name__ == "__main__":
    setup_gui()

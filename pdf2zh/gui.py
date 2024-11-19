import os
import re
import subprocess
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np
import pymupdf


def pdf_preview(file):
    doc = pymupdf.open(file)
    page = doc[0]
    pix = page.get_pixmap()
    image = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
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
    file_path, service, lang_to, page_range, extra_args, progress=gr.Progress()
):
    """Translate PDF content using selected service."""
    if not file_path:
        return None, None, gr.update(visible=False)

    progress(0, desc="Starting translation...")

    # Create a temporary working directory using Gradio's file utilities
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create safe paths using pathlib
        temp_path = Path(temp_dir)
        input_pdf = temp_path / "input.pdf"

        # Copy input file to temp directory
        progress(0.2, desc="Preparing files...")
        with open(file_path, "rb") as src, open(input_pdf, "wb") as dst:
            dst.write(src.read())

        # Map service names to pdf2zh service options
        service_map = {
            "Google": "google",
            "DeepL": "deepl",
            "DeepLX": "deeplx",
            "Ollama": "ollama:gemma2",
            "Azure": "azure",
        }
        selected_service = service_map.get(service, "google")
        lang_to = "zh"

        # Execute translation in temp directory with real-time progress
        progress(0.3, desc=f"Starting translation with {selected_service}...")

        # Create output directory for translated files
        output_dir = Path("gradio_files") / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"translated_{os.path.basename(file_path)}"
        # Prepare extra arguments
        extra_args = extra_args.strip()
        lang_to = lang_to.lower()
        if lang_to == "chinese":
            lang_to = "zh"
        elif lang_to == "english":
            lang_to = "en"
        elif lang_to == "french":
            lang_to = "fr"
        elif lang_to == "german":
            lang_to = "de"
        elif lang_to == "japanese":
            lang_to = "ja"
        elif lang_to == "korean":
            lang_to = "ko"
        elif lang_to == "russian":
            lang_to = "ru"
        elif lang_to == "spanish":
            lang_to = "es"
        else:
            lang_to = "zh"  # Default to Chinese
        # Add page range arguments
        if page_range == "All":
            extra_args += ""
        elif page_range == "First":
            extra_args += " -p 1"
        elif page_range == "First 5 pages":
            extra_args += " -p 1-5"

        # Execute translation command
        if selected_service == "google" and lang_to == "zh":
            command = (
                f'cd "{temp_path}" && pdf2zh "{input_pdf}" -lo "zh-CN" {extra_args}'
            )
        else:
            command = f'cd "{temp_path}" && pdf2zh "{input_pdf}" -lo {lang_to} -s {selected_service} {extra_args}'
        print(f"Executing command: {command}")
        print(f"Files in temp directory: {os.listdir(temp_path)}")

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
                break
            if output:
                print(f"Command output: {output.strip()}")
                # Look for percentage in output
                match = re.search(r"(\d+)%", output.strip())
                if match:
                    percent = int(match.group(1))
                    # Map command progress (0-100%) to our progress range (30-80%)
                    progress_val = 0.3 + (percent * 0.5 / 100)
                    progress(progress_val, desc=f"Translating content: {percent}%")

        # Get the return code
        return_code = process.poll()
        print(f"Command completed with return code: {return_code}")

        # Check if translation was successful
        translated_file = temp_path / f"input-{lang_to}.pdf"
        print(f"Files after translation: {os.listdir(temp_path)}")

        if not translated_file.exists():
            print(f"Translation failed: Output file not found at {translated_file}")
            return None, None, gr.update(visible=False)

        # Copy the translated file to a permanent location
        progress(0.8, desc="Saving translated file...")
        with open(translated_file, "rb") as src, open(final_output, "wb") as dst:
            dst.write(src.read())

        # Generate preview of translated PDF
        progress(0.9, desc="Generating preview...")
        try:
            translated_preview = pdf_preview(str(final_output))
        except Exception as e:
            print(f"Error generating preview: {e}")
            translated_preview = None

    progress(1.0, desc="Translation complete!")
    return str(final_output), translated_preview, gr.update(visible=True)


# Global setup
with gr.Blocks(
    title="PDF2ZH - PDF Translation with preserved formats",
    css="""
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}
    """,
) as demo:
    gr.Markdown("# PDF Translation")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## File")
            file_input = gr.File(
                label="Document",
                file_count="single",
                file_types=[".pdf"],
                type="filepath",
            )
            gr.Markdown("## Option")
            service = gr.Dropdown(
                label="Service",
                info="Which translation service to use. Some require keys",
                choices=["Google", "DeepL", "DeepLX", "Ollama", "Azure"],
                value="Google",
            )
            # lang_src = gr.Dropdown(
            #     label="Source Language",
            #     info="Which translation service to use. Some require keys",
            #     choices=["Google", "DeepL", "DeepLX", "Ollama", "Azure"],
            #     value="Google",
            # )
            lang_to = gr.Dropdown(
                label="Translate to",
                info="Which language to translate to (optional)",
                choices=[
                    "Chinese",
                    "English",
                    "French",
                    "German",
                    "Japanese",
                    "Korean",
                    "Russian",
                    "Spanish",
                ],
                value="Chinese",
            )
            page_range = gr.Radio(
                ["All", "First", "First 5 pages"],
                label="Pages",
                info="Translate the full document or just few pages (optional)",
                value="All",
            )
            extra_args = gr.Textbox(
                label="Advanced Arguments",
                info="Extra arguments supported in commandline (optional)",
                value="",
            )
            envs_status = "<span class='env-success'>- Properly configured.</span><br>"

            def details_wrapper(text_markdown):
                text = f""" 
                <details>
                    <summary>Technical details</summary>
                    {text_markdown}
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a>    
                </details>"""
                return text

            def env_var_checker(env_var_name: str) -> str:
                if (
                    not os.environ.get(env_var_name)
                    or os.environ.get(env_var_name) == ""
                ):
                    envs_status = f"<span class='env-warning'>- Warning: environmental not found or error ({env_var_name}).</span><br>- Please make sure that the environment variables are properly configured (<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
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
                    envs_status = env_var_checker("OPENAI_API_KEY")
                elif value == "Ollama":
                    envs_status = env_var_checker("OLLAMA_HOST")
                else:
                    envs_status = "<span class='env-warning'>- Warning: model not in the list.</span><br>- Please report via (<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
                return envs_status

            output_file = gr.File(label="Download Translation", visible=False)
            translate_btn = gr.Button("Translate", variant="primary", visible=False)
            tech_details_tog = gr.Markdown(
                details_wrapper(envs_status),
                elem_classes=["secondary-text"],
            )
            service.select(on_select_service, service, tech_details_tog)

        with gr.Column(scale=2):
            gr.Markdown("## Preview")
            preview = gr.Image(label="Document Preview", visible=True)

    # Event handlers
    file_input.upload(
        upload_file,
        inputs=[file_input, service],
        outputs=[file_input, preview, translate_btn],
    )

    translate_btn.click(
        translate,
        inputs=[file_input, service, lang_to, page_range, extra_args],
        outputs=[output_file, preview, output_file],
    )


def setup_gui():
    demo.launch(debug=True, inbrowser=True, share=False)


# For auto-reloading while developing
if __name__ == "__main__":
    demo.launch(debug=True, inbrowser=True, share=False)

import os
import re
import subprocess
import tempfile
from pathlib import Path

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
    file_path, service, model_id, lang, page_range, extra_args, progress=gr.Progress()
):
    """Translate PDF content using selected service."""
    if not file_path:
        return (
            None,
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

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

        selected_service = service_map.get(service, "google")
        lang_to = lang_map.get(lang, "zh")

        # Execute translation in temp directory with real-time progress
        progress(0.3, desc=f"Starting translation with {selected_service}...")

        # Create output directory for translated files
        output_dir = Path("gradio_files") / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"translated_{os.path.basename(file_path)}"
        final_output_dual = output_dir / f"dual_{os.path.basename(file_path)}"

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
            command = f'cd "{temp_path}" && pdf2zh "{input_pdf}" -lo {lang_to} -s {selected_service}:{model_id} {extra_args}'
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
        translated_file = temp_path / "input-zh.pdf" # <= Do not change filename
        dual_file = temp_path / "input-dual.pdf"
        print(f"Files after translation: {os.listdir(temp_path)}")

        if not translated_file.exists() and not dual_file.exists():
            print("Translation failed: No output files found")
            return (
                None,
                None,
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

        # Copy the translated files to permanent locations
        progress(0.8, desc="Saving translated files...")

        if translated_file.exists():
            with open(translated_file, "rb") as src, open(final_output, "wb") as dst:
                dst.write(src.read())

        if dual_file.exists():
            with open(dual_file, "rb") as src, open(final_output_dual, "wb") as dst:
                dst.write(src.read())

        # Generate preview of translated PDF
        progress(0.9, desc="Generating preview...")
        try:
            translated_preview = pdf_preview(str(final_output))
        except Exception as e:
            print(f"Error generating preview: {e}")
            translated_preview = None

    progress(1.0, desc="Translation complete!")
    return (
        str(final_output),
        translated_preview,
        str(final_output_dual),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
    )


# Global setup
with gr.Blocks(
    title="PDFMathTranslate - PDF Translation with preserved formats",
    css="""
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}
    """,
) as demo:
    gr.Markdown("# PDFMathTranslate")

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
                choices=service_map.keys(),
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
                choices=lang_map.keys(),
                value="Chinese",
            )
            page_range = gr.Radio(
                ["All", "First", "First 5 pages"],
                label="Pages",
                info="Translate the full document or just few pages (optional)",
                value="All",
            )
            model_id = gr.Textbox(
                label="Model ID",
                info="Please enter the identifier of the model you wish to use (e.g., gemma2). This identifier will be used to specify the particular model for translation.",
                # value="gemma2",
                visible=False,  # hide by default
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
                    - GitHub: <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a><br>
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
                    envs_status = "<span class='env-warning'>- Warning: model not in the list.</span><br>- Please report via (<a href='https://github.com/Byaidu/PDFMathTranslate'>guide</a>).<br>"
                return envs_status, model_visibility

            output_title = gr.Markdown("## Translated", visible=False)
            output_file = gr.File(label="Download Translation", visible=False)
            output_file_dual = gr.File(
                label="Download Translation (Dual)", visible=False
            )
            translate_btn = gr.Button("Translate", variant="primary", visible=False)
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
        outputs=[file_input, preview, translate_btn],
    )

    translate_btn.click(
        translate,
        inputs=[file_input, service, model_id, lang_to, page_range, extra_args],
        outputs=[
            output_file,
            preview,
            output_file_dual,
            output_file,
            output_file_dual,
            output_title,
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

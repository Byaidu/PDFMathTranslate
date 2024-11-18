import os
import re
import subprocess
import tempfile
from pathlib import Path

import gradio as gr
import pymupdf
import numpy as np

def pdf_preview(file):
    doc=pymupdf.open(file)
    page=doc[0]
    pix=page.get_pixmap()
    image=np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    return image

def upload_file(file, service, progress=gr.Progress()):
    """Handle file upload, validation, and initial preview."""
    if not file or not os.path.exists(file):
        return None, None, gr.update(visible=False)

    progress(0.3, desc="Converting PDF for preview...")
    try:
        # Convert first page for preview
        preview_image=pdf_preview(file)

        return file, preview_image, gr.update(visible=True)
    except Exception as e:
        print(f"Error converting PDF: {e}")
        return None, None, gr.update(visible=False)


def translate(file_path, service, progress=gr.Progress()):
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
        }
        selected_service = service_map.get(service, "google")
        lang_to = "zh"

        # Execute translation in temp directory with real-time progress
        progress(0.3, desc=f"Starting translation with {selected_service}...")

        # Create output directory for translated files
        output_dir = Path("gradio_files") / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"translated_{os.path.basename(file_path)}"

        # Execute translation command
        command = f'cd "{temp_path}" && pdf2zh "{input_pdf}" -s {selected_service}'
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
            translated_preview=pdf_preview(str(final_output))
        except Exception as e:
            print(f"Error generating preview: {e}")
            translated_preview = None

    progress(1.0, desc="Translation complete!")
    return str(final_output), translated_preview, gr.update(visible=True)

def setup_gui():
    with gr.Blocks(title="PDF Translation") as app:
        gr.Markdown("# PDF Translation")

        with gr.Row():
            with gr.Column(scale=1):
                service = gr.Dropdown(
                    label="Service",
                    choices=["Google", "DeepL", "DeepLX", "Ollama"],
                    value="Google",
                )

                file_input = gr.File(
                    label="Upload",
                    file_count="single",
                    file_types=[".pdf"],
                    type="filepath",
                )

                output_file = gr.File(label="Download Translation", visible=False)
                translate_btn = gr.Button("Translate", variant="primary", visible=False)
                # add a text description
                gr.Markdown(
                    """*Note: Please make sure that [pdf2zh](https://github.com/Byaidu/PDFMathTranslate) is correctly configured.*
                    GUI implemented by: [Rongxin](https://github.com/reycn)
                    [Early Version]
                    """
                )

            with gr.Column(scale=2):
                preview = gr.Image(label="Preview", visible=True)

        # Event handlers
        file_input.upload(
            upload_file,
            inputs=[file_input, service],
            outputs=[file_input, preview, translate_btn],
        )

        translate_btn.click(
            translate,
            inputs=[file_input, service],
            outputs=[output_file, preview, output_file],
        )

    app.launch(debug=True, inbrowser=True, share=False)

if __name__ == '__main__':
    setup_gui()
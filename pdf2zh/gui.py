import asyncio
import cgi
import logging
import shutil
import uuid
from pathlib import Path
from string import Template

import gradio as gr
import requests
from babeldoc import __version__ as babeldoc_version
from gradio_pdf import PDF

from pdf2zh import __version__
from pdf2zh.config import ConfigManager
from pdf2zh.config.model import SettingsModel
from pdf2zh.high_level import TranslationError
from pdf2zh.high_level import do_translate_async_stream

logger = logging.getLogger(__name__)

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
    "Range": None,  # User-defined range
}

# Load configuration
config_manager = ConfigManager()
try:
    # Load configuration from files and environment variables
    settings = config_manager.initialize_config()
    # Check if sensitive inputs should be disabled in GUI
    disable_sensitive_input = getattr(
        settings.basic, "disable_gui_sensitive_input", False
    )
except Exception as e:
    logger.warning(f"Could not load initial config: {e}")
    settings = SettingsModel()
    disable_sensitive_input = False

# Define default values
default_lang_from = (
    settings.translation.lang_in
    if settings.translation.lang_in != "auto"
    else "English"
)
default_lang_to = settings.translation.lang_out
for display_name, code in lang_map.items():
    if code == default_lang_to:
        default_lang_to = display_name
        break
else:
    default_lang_to = "Simplified Chinese"  # Fallback

# Available translation services
# This will eventually be dynamically determined based on available translators
available_services = ["OpenAI"]

# Map service names to translate implementation details (to be expanded)
service_config_map = {
    "OpenAI": {
        "use_openai": True,
        "sensitive_fields": ["openai_api_key", "openai_base_url"],
    }
}


def download_with_limit(url: str, save_path: str, size_limit: int = None) -> str:
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
            filename = Path(url).name
        filename = Path(filename).stem + ".pdf"
        save_path = Path(save_path)
        file_path = save_path / filename
        with file_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                total_size += len(chunk)
                if size_limit and total_size > size_limit:
                    raise gr.Error("Exceeds file size limit")
                file.write(chunk)
    return file_path


async def stop_translate_file(state: dict) -> None:
    """
    This function stops the translation process.

    Inputs:
        - state: The state of the translation process

    Returns:- None
    """
    if "current_task" not in state or state["current_task"] is None:
        return

    logger.info(
        f"Stopping translation for session {state.get('session_id', 'unknown')}"
    )
    # Cancel the task
    try:
        state["current_task"].cancel()
        # Wait briefly for cancellation to take effect
        await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error stopping translation: {e}")
    finally:
        state["current_task"] = None


async def translate_file(
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
    skip_subset_fonts,
    ignore_cache,
    state,
    openai_model=None,
    openai_base_url=None,
    openai_api_key=None,
    progress=None,
):
    """
    This function translates a PDF file from one language to another using the new architecture.

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
        - skip_subset_fonts: Whether to skip subsetting fonts
        - ignore_cache: Whether to ignore the translation cache
        - state: The state of the translation process
        - openai_model: The OpenAI model to use
        - openai_base_url: The base URL for OpenAI API
        - openai_api_key: The OpenAI API key
        - progress: The progress bar

    Returns:
        - The translated mono PDF file
        - The preview PDF file
        - The translated dual PDF file
        - The visibility state of the mono PDF output
        - The visibility state of the dual PDF output
        - The visibility state of the output title
    """
    # Setup progress tracking
    if progress is None:
        progress = gr.Progress()

    # Initialize session
    session_id = str(uuid.uuid4())
    state["session_id"] = session_id

    # Track progress
    progress(0, desc="Starting translation...")

    # Prepare output directory
    output = Path("pdf2zh_files") / session_id
    output.mkdir(parents=True, exist_ok=True)

    # Get input file path
    if file_type == "File":
        if not file_input:
            raise gr.Error("No file input provided")
        file_path = shutil.copy(file_input, output)
    else:
        if not link_input:
            raise gr.Error("No link input provided")
        try:
            file_path = download_with_limit(link_input, output)
        except Exception as e:
            raise gr.Error(f"Error downloading file: {e}") from e

    # Create settings model
    translate_settings = settings.clone()

    # Map UI language selections to language codes
    source_lang = lang_map.get(lang_from, "auto")
    target_lang = lang_map.get(lang_to, "zh")

    # Set up page selection
    if page_range == "Range" and page_input:
        pages = page_input  # The backend parser handles the format
    else:
        # Use predefined ranges from page_map
        selected_pages = page_map[page_range]
        if selected_pages is None:
            pages = None  # All pages
        else:
            # Convert page indices to comma-separated string
            pages = ",".join(
                str(p + 1) for p in selected_pages
            )  # +1 because UI is 1-indexed

    # Update settings with UI values
    translate_settings.basic.input_files = {str(file_path)}
    translate_settings.report_interval = 0.2
    translate_settings.translation.lang_in = source_lang
    translate_settings.translation.lang_out = target_lang
    translate_settings.translation.pages = pages
    translate_settings.translation.output = str(output)
    translate_settings.translation.qps = int(threads)
    translate_settings.translation.ignore_cache = ignore_cache
    translate_settings.pdf.skip_clean = skip_subset_fonts

    # Set service-specific settings
    if service == "OpenAI":
        translate_settings.openai = True
        # Only update sensitive fields if they're provided and not disabled
        if not disable_sensitive_input:
            if openai_model:
                translate_settings.openai_detail.openai_model = openai_model
            if openai_base_url:
                translate_settings.openai_detail.openai_base_url = openai_base_url
            if openai_api_key and openai_api_key != "***":
                translate_settings.openai_detail.openai_api_key = openai_api_key
    else:
        # Handle other services when implemented
        pass

    # Add custom prompt if provided
    if prompt:
        # This might need adjustment based on how prompt is handled in the new system
        translate_settings.custom_prompt = Template(prompt)

    # Validate settings before proceeding
    try:
        translate_settings.validate_settings()
    except ValueError as e:
        raise gr.Error(f"Invalid settings: {e}") from e

    # Create a function to process events and update progress
    async def process_translation():
        mono_path = None
        dual_path = None

        try:
            async for event in do_translate_async_stream(
                translate_settings, Path(file_path)
            ):
                if event["type"] in (
                    "progress_start",
                    "progress_update",
                    "progress_end",
                ):
                    # Update progress bar
                    desc = event["stage"]
                    progress_value = event["overall_progress"] / 100.0
                    part_index = event["part_index"]
                    total_parts = event["total_parts"]
                    desc = f"{desc} ({part_index}/{total_parts})"
                    logger.info(f"Progress: {progress_value}, {desc}")
                    progress(progress_value, desc=desc)
                elif event["type"] == "finish":
                    # Extract result paths
                    result = event["translate_result"]
                    mono_path = result.mono_pdf_path
                    dual_path = result.dual_pdf_path
                    progress(1.0, desc="Translation complete!")
                    break
                elif event["type"] == "error":
                    # Handle error event
                    error_msg = event.get("error", "Unknown error")
                    error_details = event.get("details", "")
                    error_str = f"{error_msg}" + (
                        f": {error_details}" if error_details else ""
                    )
                    raise gr.Error(f"Translation error: {error_str}")
        except asyncio.CancelledError:
            # Handle task cancellation
            logger.info(f"Translation for session {session_id} was cancelled")
            raise gr.Error("Translation was cancelled") from None
        except TranslationError as e:
            # Handle structured translation errors
            logger.error(f"Translation error: {e}")
            raise gr.Error(f"Translation error: {e}") from e
        except Exception as e:
            # Handle other exceptions
            logger.error(f"Error in translate_file: {e}", exc_info=True)
            raise gr.Error(f"Translation failed: {e}") from e

        return mono_path, dual_path

    # Create and store the task
    task = asyncio.create_task(process_translation())
    state["current_task"] = task

    try:
        # Wait for the translation to complete
        mono_path, dual_path = await task

        # Return results to update UI
        return (
            str(mono_path) if mono_path else None,  # Output mono file
            str(mono_path) if mono_path else None,  # Preview
            str(dual_path) if dual_path else None,  # Output dual file
            gr.update(visible=bool(mono_path)),  # Show mono download if available
            gr.update(visible=bool(dual_path)),  # Show dual download if available
            gr.update(
                visible=bool(mono_path or dual_path)
            ),  # Show output title if any output
        )
    except gr.Error as e:
        # Forward Gradio errors
        raise
    except asyncio.CancelledError:
        # Return None for all outputs if cancelled
        return (
            None,
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )
    except Exception as e:
        # Catch any other errors
        logger.error(f"Error in translate_file: {e}", exc_info=True)
        raise gr.Error(f"Translation failed: {e}") from e
    finally:
        # Clear task reference
        state["current_task"] = None


# Custom theme definition
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
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}

    /* Add dashed border to input-file class */
    .input-file {
        border: 1.2px dashed #165DFF !important;
        border-radius: 6px !important;
    }

    .progress-bar-wrap {
        border-radius: 8px !important;
    }

    .progress-bar {
        border-radius: 8px !important;
    }

    .pdf-canvas canvas {
        width: 100%;
    }
    """

tech_details_string = f"""
                    <summary>Technical details</summary>
                    - GitHub: <a href="https://github.com/Byaidu/PDFMathTranslate">Byaidu/PDFMathTranslate</a><br>
                    - BabelDOC: <a href="https://github.com/funstory-ai/BabelDOC">funstory-ai/BabelDOC</a><br>
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a><br>
                    - pdf2zh Version: {__version__} <br>
                    - BabelDOC Version: {babeldoc_version}
                """

# The following code creates the GUI
with gr.Blocks(
    title="PDFMathTranslate - PDF Translation with preserved formats",
    theme=gr.themes.Default(
        primary_hue=custom_blue, spacing_size="md", radius_size="lg"
    ),
    css=custom_css,
) as demo:
    gr.Markdown(
        "# [PDFMathTranslate @ GitHub](https://github.com/Byaidu/PDFMathTranslate)"
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## File")
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

            gr.Markdown("## Translation Options")
            service = gr.Dropdown(
                label="Service",
                choices=available_services,
                value=available_services[0] if available_services else None,
            )

            with gr.Row():
                lang_from = gr.Dropdown(
                    label="Translate from",
                    choices=list(lang_map.keys()),
                    value=default_lang_from,
                )
                lang_to = gr.Dropdown(
                    label="Translate to",
                    choices=list(lang_map.keys()),
                    value=default_lang_to,
                )

            page_range = gr.Radio(
                choices=list(page_map.keys()),
                label="Pages",
                value=list(page_map.keys())[0],
            )

            page_input = gr.Textbox(
                label="Page range (e.g., 1,3,5-10,-5)",
                visible=False,
                interactive=True,
                placeholder="e.g., 1,3,5-10",
            )

            # OpenAI specific settings (initially visible if OpenAI is default)
            with gr.Group(visible=(service.value == "OpenAI")) as openai_settings:
                openai_model = gr.Textbox(
                    label="OpenAI Model",
                    value=settings.openai_detail.openai_model,
                    interactive=True,
                )
                openai_base_url = gr.Textbox(
                    label="OpenAI Base URL (optional)",
                    value=settings.openai_detail.openai_base_url or "",
                    interactive=not disable_sensitive_input,
                    visible=not disable_sensitive_input,
                )
                openai_api_key = gr.Textbox(
                    label="OpenAI API Key",
                    type="password",
                    value="***" if settings.openai_detail.openai_api_key else "",
                    interactive=not disable_sensitive_input,
                    visible=not disable_sensitive_input,
                )

            # Additional translation options
            with gr.Accordion("Advanced Options", open=False):
                threads = gr.Number(
                    label="Threads (QPS)",
                    value=settings.translation.qps or 4,
                    precision=0,
                    minimum=1,
                    interactive=True,
                )

                # PDF options
                skip_subset_fonts = gr.Checkbox(
                    label="Skip font subsetting",
                    value=settings.pdf.skip_clean,
                    interactive=True,
                )

                ignore_cache = gr.Checkbox(
                    label="Ignore cache",
                    value=settings.translation.ignore_cache,
                    interactive=True,
                )

                prompt = gr.Textbox(
                    label="Custom Prompt for LLM",
                    interactive=True,
                    placeholder="Optional: Add custom prompt for the translation model",
                )

            output_title = gr.Markdown("## Translated", visible=False)
            output_file_mono = gr.File(
                label="Download Translation (Mono)", visible=False
            )
            output_file_dual = gr.File(
                label="Download Translation (Dual)", visible=False
            )

            translate_btn = gr.Button("Translate", variant="primary")
            cancel_btn = gr.Button("Cancel", variant="secondary")

            tech_details = gr.Markdown(
                tech_details_string,
                elem_classes=["secondary-text"],
            )

        with gr.Column(scale=2):
            gr.Markdown("## Preview")
            preview = PDF(label="Document Preview", visible=True, height=2000)

    # Event handlers
    def on_select_filetype(file_type):
        """Update visibility based on selected file type"""
        return (
            gr.update(visible=file_type == "File"),
            gr.update(visible=file_type == "Link"),
        )

    def on_select_page(choice):
        """Update page input visibility based on selection"""
        return gr.update(visible=choice == "Range")

    def on_select_service(service_name):
        """Update service-specific settings visibility"""
        # For now, we only have OpenAI
        if service_name == "OpenAI":
            return gr.update(visible=True)
        return gr.update(visible=False)

    # Default file handler
    file_input.upload(
        lambda x: x,
        inputs=file_input,
        outputs=preview,
    )

    # Event bindings
    file_type.select(
        on_select_filetype,
        file_type,
        [file_input, link_input],
    )

    page_range.select(
        on_select_page,
        page_range,
        page_input,
    )

    service.select(
        on_select_service,
        service,
        openai_settings,
    )

    # State for managing translation tasks
    state = gr.State({"session_id": None, "current_task": None})

    # Translation button click handler
    translate_btn.click(
        translate_file,
        inputs=[
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
            skip_subset_fonts,
            ignore_cache,
            state,
            # OpenAI specific settings
            openai_model,
            openai_base_url,
            openai_api_key,
        ],
        outputs=[
            output_file_mono,  # Mono PDF file
            preview,  # Preview
            output_file_dual,  # Dual PDF file
            output_file_mono,  # Visibility of mono output
            output_file_dual,  # Visibility of dual output
            output_title,  # Visibility of output title
        ],
    )

    # Cancel button click handler
    cancel_btn.click(
        stop_translate_file,
        inputs=[state],
    )


def parse_user_passwd(file_path: list) -> tuple[list, str]:
    """
    This function parses a user password file.

    Inputs:
        - file_path: The path to the file

    Returns:
        - A tuple containing the user list and HTML
    """
    content = ""
    if len(file_path) == 2:
        try:
            path = Path(file_path[1])
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Error: File '{file_path[1]}' not found.")
    try:
        path = Path(file_path[0])
        tuple_list = [
            tuple(line.strip().split(","))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        tuple_list = []
    return tuple_list, content


def setup_gui(
    share: bool = False, auth_file: list | None = None, server_port=7860
) -> None:
    """
    This function sets up the GUI for the application.

    Inputs:
        - share: Whether to share the GUI
        - auth_file: The authentication file
        - server_port: The port to run the server on

    Returns:
        - None
    """

    user_list = None
    html = None

    if auth_file:
        user_list, html = parse_user_passwd(auth_file)

    if not auth_file or not user_list:
        try:
            demo.launch(
                server_name="0.0.0.0",
                debug=True,
                inbrowser=True,
                share=share,
                server_port=server_port,
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
                    server_port=server_port,
                )
            except Exception:
                print(
                    "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                )
                demo.launch(
                    debug=True, inbrowser=True, share=True, server_port=server_port
                )
    else:
        try:
            demo.launch(
                server_name="0.0.0.0",
                debug=True,
                inbrowser=True,
                share=share,
                auth=user_list,
                auth_message=html,
                server_port=server_port,
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
                    server_port=server_port,
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
                    server_port=server_port,
                )


# For auto-reloading while developing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    setup_gui()

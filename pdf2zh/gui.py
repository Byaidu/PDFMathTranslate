import asyncio
import cgi
import logging
import shutil
import typing
import uuid
from pathlib import Path
from string import Template

import gradio as gr
import requests
from babeldoc import __version__ as babeldoc_version
from gradio_pdf import PDF

from pdf2zh import __version__
from pdf2zh.config import ConfigManager
from pdf2zh.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh.config.model import SettingsModel
from pdf2zh.config.translate_engine_model import GUI_PASSWORD_FIELDS
from pdf2zh.config.translate_engine_model import GUI_SENSITIVE_FIELDS
from pdf2zh.config.translate_engine_model import TRANSLATION_ENGINE_METADATA
from pdf2zh.config.translate_engine_model import TRANSLATION_ENGINE_METADATA_MAP
from pdf2zh.high_level import TranslationError
from pdf2zh.high_level import do_translate_async_stream

logger = logging.getLogger(__name__)
__gui_service_arg_names = []
# The following variables associate strings with specific languages
lang_map = {
    "English": "en",
    "Simplified Chinese": "zh-CN",
    "Traditional Chinese - Hong Kong": "zh-HK",
    "Traditional Chinese - Taiwan": "zh-TW",
    "Japanese": "ja",
    "Korean": "ko",
    "Polish": "pl",
    "Russian": "ru",
    "Spanish": "es",
    "Portuguese": "pt",
    "French": "fr",
    "Malay": "ms",
    "Indonesian": "id",
    "Turkmen": "tk",
    "Filipino (Tagalog)": "tl",
    "Vietnamese": "vi",
    "Kazakh (Latin)": "kk",
    "German": "de",
    "Dutch": "nl",
    "Irish": "ga",
    "Italian": "it",
    "Greek": "el",
    "Swedish": "sv",
    "Danish": "da",
    "Norwegian": "no",
    "Icelandic": "is",
    "Finnish": "fi",
    "Ukrainian": "uk",
    "Czech": "cs",
    "Romanian": "ro",  # Covers Romanian, Moldovan, Moldovan (Cyrillic)
    "Hungarian": "hu",
    "Slovak": "sk",
    "Croatian": "hr",  # Also listed later, keep first
    "Estonian": "et",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Belarusian": "be",
    "Macedonian": "mk",
    "Albanian": "sq",
    "Serbian (Cyrillic)": "sr",  # Covers Serbian (Latin) too
    "Slovenian": "sl",
    "Catalan": "ca",
    "Bulgarian": "bg",
    "Maltese": "mt",
    "Swahili": "sw",
    "Amharic": "am",
    "Oromo": "om",
    "Tigrinya": "ti",
    "Haitian Creole": "ht",
    "Latin": "la",
    "Lao": "lo",
    "Malayalam": "ml",
    "Gujarati": "gu",
    "Thai": "th",
    "Burmese": "my",
    "Tamil": "ta",
    "Telugu": "te",
    "Oriya": "or",  # Also listed later, keep first
    "Armenian": "hy",
    "Mongolian (Cyrillic)": "mn",
    "Georgian": "ka",
    "Khmer": "km",
    "Bosnian": "bs",
    "Luxembourgish": "lb",
    "Romansh": "rm",
    "Turkish": "tr",
    "Sinhala": "si",
    "Uzbek": "uz",
    "Kyrgyz": "ky",  # Listed as Kirghiz later, keep this one
    "Tajik": "tg",
    "Abkhazian": "ab",
    "Afar": "aa",
    "Afrikaans": "af",
    "Akan": "ak",
    "Aragonese": "an",
    "Avaric": "av",
    "Ewe": "ee",
    "Aymara": "ay",
    "Ojibwa": "oj",
    "Occitan": "oc",
    "Ossetian": "os",
    "Pali": "pi",
    "Bashkir": "ba",
    "Basque": "eu",
    "Breton": "br",
    "Chamorro": "ch",
    "Chechen": "ce",
    "Chuvash": "cv",
    "Tswana": "tn",
    "Ndebele, South": "nr",
    "Ndonga": "ng",
    "Faroese": "fo",
    "Fijian": "fj",
    "Frisian, Western": "fy",
    "Ganda": "lg",
    "Kongo": "kg",
    "Kalaallisut": "kl",
    "Church Slavic": "cu",
    "Guarani": "gn",
    "Interlingua": "ia",
    "Herero": "hz",
    "Kikuyu": "ki",
    "Rundi": "rn",
    "Kinyarwanda": "rw",
    "Galician": "gl",
    "Kanuri": "kr",
    "Cornish": "kw",
    "Komi": "kv",
    "Xhosa": "xh",
    "Corsican": "co",
    "Cree": "cr",
    "Quechua": "qu",
    "Kurdish (Latin)": "ku",
    "Kuanyama": "kj",
    "Limburgan": "li",
    "Lingala": "ln",
    "Manx": "gv",
    "Malagasy": "mg",
    "Marshallese": "mh",
    "Maori": "mi",
    "Navajo": "nv",
    "Nauru": "na",
    "Nyanja": "ny",
    "Norwegian Nynorsk": "nn",
    "Sardinian": "sc",
    "Northern Sami": "se",
    "Samoan": "sm",
    "Sango": "sg",
    "Shona": "sn",
    "Esperanto": "eo",
    "Scottish Gaelic": "gd",
    "Somali": "so",
    "Southern Sotho": "st",
    "Tatar": "tt",
    "Tahitian": "ty",
    "Tongan": "to",
    "Twi": "tw",
    "Walloon": "wa",
    "Welsh": "cy",
    "Venda": "ve",
    "Volapük": "vo",
    "Interlingue": "ie",
    "Hiri Motu": "ho",
    "Igbo": "ig",
    "Ido": "io",
    "Inuktitut": "iu",
    "Inupiaq": "ik",
    "Sichuan Yi": "ii",
    "Yoruba": "yo",
    "Zhuang": "za",
    "Tsonga": "ts",
    "Zulu": "zu",
}

rev_lang_map = {v: k for k, v in lang_map.items()}

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
    settings = config_manager.initialize_cli_config()
    # Check if sensitive inputs should be disabled in GUI
    disable_sensitive_input = settings.gui_settings.disable_gui_sensitive_input
except Exception as e:
    logger.warning(f"Could not load initial config: {e}")
    settings = CLIEnvSettingsModel()
    disable_sensitive_input = False

# Define default values
default_lang_from = rev_lang_map.get(settings.translation.lang_in, "English")

default_lang_to = settings.translation.lang_out
for display_name, code in lang_map.items():
    if code == default_lang_to:
        default_lang_to = display_name
        break
else:
    default_lang_to = "Simplified Chinese"  # Fallback

# Available translation services
# This will eventually be dynamically determined based on available translators
available_services = [x.translate_engine_type for x in TRANSLATION_ENGINE_METADATA]

if settings.gui_settings.enabled_services:
    enabled_services = set(settings.gui_settings.enabled_services.split(","))
    available_services = [x for x in available_services if x in enabled_services]

assert available_services, "No translation service is enabled"


disable_gui_sensitive_input = settings.gui_settings.disable_gui_sensitive_input


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


def _prepare_input_file(
    file_type: str, file_input: str, link_input: str, output_dir: Path
) -> Path:
    """
    This function prepares the input file for translation.

    Inputs:
        - file_type: The type of file to translate (File or Link)
        - file_input: The path to the file to translate
        - link_input: The link to the file to translate
        - output_dir: The directory to save the file to

    Returns:
        - The path of the input file
    """
    if file_type == "File":
        if not file_input:
            raise gr.Error("No file input provided")
        file_path = shutil.copy(file_input, output_dir)
    else:
        if not link_input:
            raise gr.Error("No link input provided")
        try:
            file_path = download_with_limit(link_input, output_dir)
        except Exception as e:
            raise gr.Error(f"Error downloading file: {e}") from e

    return Path(file_path)


def _build_translate_settings(
    base_settings: CLIEnvSettingsModel,
    file_path: Path,
    output_dir: Path,
    ui_inputs: dict,
) -> SettingsModel:
    """
    This function builds translation settings from UI inputs.

    Inputs:
        - base_settings: The base settings model to build upon
        - file_path: The path to the input file
        - output_dir: The output directory
        - ui_inputs: A dictionary of UI inputs

    Returns:
        - A configured SettingsModel instance
    """
    # Clone base settings to avoid modifying the original
    translate_settings = base_settings.clone()
    original_output = translate_settings.translation.output
    original_pages = translate_settings.pdf.pages
    original_gui_settings = config_manager.config_cli_settings.gui_settings

    # Extract UI values
    service = ui_inputs.get("service")
    lang_from = ui_inputs.get("lang_from")
    lang_to = ui_inputs.get("lang_to")
    page_range = ui_inputs.get("page_range")
    page_input = ui_inputs.get("page_input")
    prompt = ui_inputs.get("prompt")
    threads = ui_inputs.get("threads")
    ignore_cache = ui_inputs.get("ignore_cache")

    # PDF Output Options
    no_mono = ui_inputs.get("no_mono")
    no_dual = ui_inputs.get("no_dual")
    dual_translate_first = ui_inputs.get("dual_translate_first")
    use_alternating_pages_dual = ui_inputs.get("use_alternating_pages_dual")
    watermark_output_mode = ui_inputs.get("watermark_output_mode")

    # Advanced Translation Options
    min_text_length = ui_inputs.get("min_text_length")
    rpc_doclayout = ui_inputs.get("rpc_doclayout")

    # Advanced PDF Options
    skip_clean = ui_inputs.get("skip_clean")
    disable_rich_text_translate = ui_inputs.get("disable_rich_text_translate")
    enhance_compatibility = ui_inputs.get("enhance_compatibility")
    split_short_lines = ui_inputs.get("split_short_lines")
    short_line_split_factor = ui_inputs.get("short_line_split_factor")
    translate_table_text = ui_inputs.get("translate_table_text")
    skip_scanned_detection = ui_inputs.get("skip_scanned_detection")
    ocr_workaround = ui_inputs.get("ocr_workaround")
    max_pages_per_part = ui_inputs.get("max_pages_per_part")
    formular_font_pattern = ui_inputs.get("formular_font_pattern")
    formular_char_pattern = ui_inputs.get("formular_char_pattern")

    # New input for custom_system_prompt
    custom_system_prompt_input = ui_inputs.get("custom_system_prompt_input")

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
    translate_settings.translation.output = str(output_dir)
    translate_settings.translation.qps = int(threads)
    translate_settings.translation.ignore_cache = ignore_cache

    # Update Translation Settings
    if min_text_length is not None:
        translate_settings.translation.min_text_length = int(min_text_length)
    if rpc_doclayout:
        translate_settings.translation.rpc_doclayout = rpc_doclayout

    # Update PDF Settings
    translate_settings.pdf.pages = pages
    translate_settings.pdf.no_mono = no_mono
    translate_settings.pdf.no_dual = no_dual
    translate_settings.pdf.dual_translate_first = dual_translate_first
    translate_settings.pdf.use_alternating_pages_dual = use_alternating_pages_dual

    # Map watermark mode from UI to enum
    if watermark_output_mode == "Watermarked":
        from pdf2zh.config.model import WatermarkOutputMode

        translate_settings.pdf.watermark_output_mode = WatermarkOutputMode.Watermarked
    elif watermark_output_mode == "No Watermark":
        from pdf2zh.config.model import WatermarkOutputMode

        translate_settings.pdf.watermark_output_mode = WatermarkOutputMode.NoWatermark

    # Update Advanced PDF Settings
    translate_settings.pdf.skip_clean = skip_clean
    translate_settings.pdf.disable_rich_text_translate = disable_rich_text_translate
    translate_settings.pdf.enhance_compatibility = enhance_compatibility
    translate_settings.pdf.split_short_lines = split_short_lines
    translate_settings.pdf.ocr_workaround = ocr_workaround
    if short_line_split_factor is not None:
        translate_settings.pdf.short_line_split_factor = float(short_line_split_factor)

    translate_settings.pdf.translate_table_text = translate_table_text
    translate_settings.pdf.skip_scanned_detection = skip_scanned_detection

    if max_pages_per_part is not None and max_pages_per_part > 0:
        translate_settings.pdf.max_pages_per_part = int(max_pages_per_part)

    if formular_font_pattern:
        translate_settings.pdf.formular_font_pattern = formular_font_pattern

    if formular_char_pattern:
        translate_settings.pdf.formular_char_pattern = formular_char_pattern

    assert service in TRANSLATION_ENGINE_METADATA_MAP, "UNKNOW TRANSLATION ENGINE!"

    for metadata in TRANSLATION_ENGINE_METADATA:
        cli_flag = metadata.cli_flag_name
        setattr(translate_settings, cli_flag, False)

    metadata = TRANSLATION_ENGINE_METADATA_MAP[service]
    cli_flag = metadata.cli_flag_name
    setattr(translate_settings, cli_flag, True)
    if metadata.cli_detail_field_name:
        detail_setting = getattr(translate_settings, metadata.cli_detail_field_name)
        if metadata.setting_model_type:
            for field_name in metadata.setting_model_type.model_fields:
                if field_name == "translate_engine_type":
                    continue
                if disable_gui_sensitive_input:
                    if field_name in GUI_PASSWORD_FIELDS:
                        continue
                    if field_name in GUI_SENSITIVE_FIELDS:
                        continue
                value = ui_inputs.get(field_name)
                type_hint = detail_setting.model_fields[field_name].annotation
                original_type = typing.get_origin(type_hint)
                type_args = typing.get_args(type_hint)
                if type_hint is str or str in type_args:
                    pass
                elif type_hint is int or int in type_args:
                    value = int(value)
                elif type_hint is bool or bool in type_args:
                    value = bool(value)
                else:
                    raise Exception(
                        f"Unsupported type {type_hint} for field {field_name} in gui translation engine settings"
                    )
                setattr(detail_setting, field_name, value)

    # Add custom prompt if provided
    if prompt:
        # This might need adjustment based on how prompt is handled in the new system
        translate_settings.custom_prompt = Template(prompt)

    # Add custom system prompt if provided
    custom_system_prompt_value = ui_inputs.get("custom_system_prompt_input")
    if custom_system_prompt_value:
        translate_settings.translation.custom_system_prompt = custom_system_prompt_value
    else:
        translate_settings.translation.custom_system_prompt = None

    # Validate settings before proceeding
    try:
        translate_settings.validate_settings()
        settings = translate_settings.to_settings_model()
        translate_settings.translation.output = original_output
        translate_settings.pdf.pages = original_pages
        translate_settings.gui_settings = original_gui_settings
        if not settings.gui_settings.disable_config_auto_save:
            config_manager.write_user_default_config_file(settings=translate_settings)
        settings.validate_settings()
        return settings
    except ValueError as e:
        raise gr.Error(f"Invalid settings: {e}") from e


async def _run_translation_task(
    settings: SettingsModel, file_path: Path, state: dict, progress: gr.Progress
) -> tuple[Path | None, Path | None]:
    """
    This function runs the translation task and handles progress updates.

    Inputs:
        - settings: The translation settings
        - file_path: The path to the input file
        - state: The state dictionary for tracking the task
        - progress: The Gradio progress bar

    Returns:
        - A tuple of (mono_pdf_path, dual_pdf_path)
    """
    mono_path = None
    dual_path = None

    try:
        settings.basic.input_files = set()
        async for event in do_translate_async_stream(settings, file_path):
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
                stage_current = event["stage_current"]
                stage_total = event["stage_total"]
                desc = f"{desc} ({part_index}/{total_parts}, {stage_current}/{stage_total})"
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
        # Handle task cancellation - let translate_file handle the UI updates
        logger.info(
            f"Translation for session {state.get('session_id', 'unknown')} was cancelled"
        )
        raise  # Re-raise for the calling function to handle
    except TranslationError as e:
        # Handle structured translation errors
        logger.error(f"Translation error: {e}")
        raise gr.Error(f"Translation error: {e}") from e
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in _run_translation_task: {e}", exc_info=True)
        raise gr.Error(f"Translation failed: {e}") from e

    return mono_path, dual_path


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
    # PDF Output Options
    no_mono,
    no_dual,
    dual_translate_first,
    use_alternating_pages_dual,
    watermark_output_mode,
    # Advanced Options
    prompt,
    threads,
    min_text_length,
    rpc_doclayout,
    # New input for custom_system_prompt
    custom_system_prompt_input,
    skip_clean,
    disable_rich_text_translate,
    enhance_compatibility,
    split_short_lines,
    short_line_split_factor,
    translate_table_text,
    skip_scanned_detection,
    max_pages_per_part,
    formular_font_pattern,
    formular_char_pattern,
    ignore_cache,
    state,
    ocr_workaround,
    *translation_engine_arg_inputs,
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
        - skip_clean: Whether to skip subsetting fonts
        - ignore_cache: Whether to ignore the translation cache
        - state: The state of the translation process
        - translation_engine_arg_inputs: The translator engine args
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

    # Initialize session and output directory
    session_id = str(uuid.uuid4())
    state["session_id"] = session_id

    # Track progress
    progress(0, desc="Starting translation...")

    # Prepare output directory
    output_dir = Path("pdf2zh_files") / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collection of UI inputs for config building
    ui_inputs = {
        "service": service,
        "lang_from": lang_from,
        "lang_to": lang_to,
        "page_range": page_range,
        "page_input": page_input,
        # PDF Output Options
        "no_mono": no_mono,
        "no_dual": no_dual,
        "dual_translate_first": dual_translate_first,
        "use_alternating_pages_dual": use_alternating_pages_dual,
        "watermark_output_mode": watermark_output_mode,
        # Advanced Options
        "prompt": prompt,
        "threads": threads,
        "min_text_length": min_text_length,
        "rpc_doclayout": rpc_doclayout,
        "custom_system_prompt_input": custom_system_prompt_input,
        "skip_clean": skip_clean,
        "disable_rich_text_translate": disable_rich_text_translate,
        "enhance_compatibility": enhance_compatibility,
        "split_short_lines": split_short_lines,
        "short_line_split_factor": short_line_split_factor,
        "translate_table_text": translate_table_text,
        "skip_scanned_detection": skip_scanned_detection,
        "max_pages_per_part": max_pages_per_part,
        "formular_font_pattern": formular_font_pattern,
        "formular_char_pattern": formular_char_pattern,
        "ignore_cache": ignore_cache,
        "ocr_workaround": ocr_workaround,
    }
    for arg_name, arg_input in zip(
        __gui_service_arg_names, translation_engine_arg_inputs, strict=False
    ):
        ui_inputs[arg_name] = arg_input
    try:
        # Step 1: Prepare input file
        file_path = _prepare_input_file(file_type, file_input, link_input, output_dir)

        # Step 2: Build translation settings
        translate_settings = _build_translate_settings(
            settings.clone(), file_path, output_dir, ui_inputs
        )

        # Step 3: Create and run the translation task
        task = asyncio.create_task(
            _run_translation_task(translate_settings, file_path, state, progress)
        )
        state["current_task"] = task

        # Wait for the translation to complete
        mono_path, dual_path = await task
        if not mono_path.exists():
            mono_path = None
        else:
            mono_path = mono_path.as_posix()
        if not dual_path or not dual_path.exists():
            dual_path = None
        else:
            dual_path = dual_path.as_posix()
        # Build success UI updates
        return (
            str(mono_path) if mono_path else None,  # Output mono file
            str(mono_path) if mono_path else dual_path,  # Preview
            str(dual_path) if dual_path else None,  # Output dual file
            gr.update(visible=bool(mono_path)),  # Show mono download if available
            gr.update(visible=bool(dual_path)),  # Show dual download if available
            gr.update(
                visible=bool(mono_path or dual_path)
            ),  # Show output title if any output
        )
    except asyncio.CancelledError:
        gr.Info("Translation cancelled")
        # Return None for all outputs if cancelled
        return (
            None,
            None,
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )
    except gr.Error:
        # Re-raise Gradio errors without modification
        raise
    except Exception as e:
        # Catch any other errors and wrap in gr.Error
        logger.exception(f"Error in translate_file: {e}")
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
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a> & <a href="https://github.com/hellofinch">hellofinch</a> & <a href="https://github.com/awwaawwa">awwaawwa</a><br>
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

    translation_engine_arg_inputs = []
    detail_text_inputs = []
    detail_text_input_index_map = {}
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
            detail_index = 0
            with gr.Group() as translation_engine_settings:
                service = gr.Dropdown(
                    label="Service",
                    choices=available_services,
                    value=available_services[0],
                )
                __gui_service_arg_names = []
                for service_name in available_services:
                    metadata = TRANSLATION_ENGINE_METADATA_MAP[service_name]
                    if not metadata.cli_detail_field_name:
                        # no detail field, no need to show
                        continue
                    detail_settings = getattr(settings, metadata.cli_detail_field_name)
                    visible = service.value == metadata.translate_engine_type
                    # OpenAI specific settings (initially visible if OpenAI is default)
                    with gr.Group(visible=True) as service_detail:
                        detail_text_input_index_map[metadata.translate_engine_type] = []

                        for (
                            field_name,
                            field,
                        ) in metadata.setting_model_type.model_fields.items():
                            if disable_gui_sensitive_input:
                                if field_name in GUI_SENSITIVE_FIELDS:
                                    continue
                                if field_name in GUI_PASSWORD_FIELDS:
                                    continue
                            if field.default_factory:
                                continue

                            if field_name == "translate_engine_type":
                                continue
                            type_hint = field.annotation
                            original_type = typing.get_origin(type_hint)
                            type_args = typing.get_args(type_hint)
                            value = getattr(detail_settings, field_name)
                            if (
                                type_hint is str
                                or str in type_args
                                or type_hint is int
                                or int in type_args
                            ):
                                if field_name in GUI_PASSWORD_FIELDS:
                                    field_input = gr.Textbox(
                                        label=field.description,
                                        value=value,
                                        interactive=True,
                                        type="password",
                                        visible=visible,
                                    )
                                else:
                                    field_input = gr.Textbox(
                                        label=field.description,
                                        value=value,
                                        interactive=True,
                                        visible=visible,
                                    )
                            elif type_hint is bool or bool in type_args:
                                field_input = gr.Checkbox(
                                    label=field.description,
                                    value=value,
                                    interactive=True,
                                    visible=visible,
                                )
                            else:
                                raise Exception(
                                    f"Unsupported type {type_hint} for field {field_name} in gui translation engine settings"
                                )
                            detail_text_input_index_map[
                                metadata.translate_engine_type
                            ].append(detail_index)
                            detail_index += 1
                            detail_text_inputs.append(field_input)
                            __gui_service_arg_names.append(field_name)
                            translation_engine_arg_inputs.append(field_input)

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

            # PDF Output Options
            gr.Markdown("## PDF Output Options")
            with gr.Row():
                no_mono = gr.Checkbox(
                    label="Disable monolingual output",
                    value=settings.pdf.no_mono,
                    interactive=True,
                )
                no_dual = gr.Checkbox(
                    label="Disable bilingual output",
                    value=settings.pdf.no_dual,
                    interactive=True,
                )

            with gr.Row():
                dual_translate_first = gr.Checkbox(
                    label="Put translated pages first in dual mode",
                    value=settings.pdf.dual_translate_first,
                    interactive=True,
                )
                use_alternating_pages_dual = gr.Checkbox(
                    label="Use alternating pages for dual PDF",
                    value=settings.pdf.use_alternating_pages_dual,
                    interactive=True,
                )

            watermark_output_mode = gr.Radio(
                choices=["Watermarked", "No Watermark"],
                label="Watermark mode",
                value="Watermarked"
                if settings.pdf.watermark_output_mode.value == "watermarked"
                else "No Watermark",
            )

            # Additional translation options
            with gr.Accordion("Advanced Options", open=False):
                prompt = gr.Textbox(
                    label="Custom prompt for translation",
                    value="",
                    visible=False,
                    interactive=True,
                    placeholder="Custom prompt for the translator",
                )

                threads = gr.Number(
                    label="RPS (Requests Per Second)",
                    value=settings.translation.qps or 4,
                    precision=0,
                    minimum=1,
                    interactive=True,
                )

                # New Textbox for custom_system_prompt
                custom_system_prompt_input = gr.Textbox(
                    label="Custom System Prompt",
                    value=settings.translation.custom_system_prompt or "",
                    interactive=True,
                    placeholder="e.g. /no_think You are a professional, authentic machine translation engine.",
                )

                min_text_length = gr.Number(
                    label="Minimum text length to translate",
                    value=settings.translation.min_text_length,
                    precision=0,
                    minimum=0,
                    interactive=True,
                )

                rpc_doclayout = gr.Textbox(
                    label="RPC service for document layout analysis (optional)",
                    value=settings.translation.rpc_doclayout or "",
                    visible=False,
                    interactive=True,
                    placeholder="http://host:port",
                )

                # PDF options section
                gr.Markdown("### PDF Options")

                skip_clean = gr.Checkbox(
                    label="Skip clean (maybe improve compatibility)",
                    value=settings.pdf.skip_clean,
                    interactive=True,
                )

                disable_rich_text_translate = gr.Checkbox(
                    label="Disable rich text translation (maybe improve compatibility)",
                    value=settings.pdf.disable_rich_text_translate,
                    interactive=True,
                )

                enhance_compatibility = gr.Checkbox(
                    label="Enhance compatibility (auto-enables skip_clean and disable_rich_text)",
                    value=settings.pdf.enhance_compatibility,
                    interactive=True,
                )

                split_short_lines = gr.Checkbox(
                    label="Force split short lines into different paragraphs",
                    value=settings.pdf.split_short_lines,
                    interactive=True,
                )

                short_line_split_factor = gr.Slider(
                    label="Split threshold factor for short lines",
                    value=settings.pdf.short_line_split_factor,
                    minimum=0.1,
                    maximum=1.0,
                    step=0.1,
                    interactive=True,
                    visible=settings.pdf.split_short_lines,
                )

                translate_table_text = gr.Checkbox(
                    label="Translate table text (experimental)",
                    value=settings.pdf.translate_table_text,
                    interactive=True,
                )

                skip_scanned_detection = gr.Checkbox(
                    label="Skip scanned detection",
                    value=settings.pdf.skip_scanned_detection,
                    interactive=True,
                )

                ocr_workaround = gr.Checkbox(
                    label="OCR workaround (experimental, will auto enable Skip scanned detection in backend)",
                    value=settings.pdf.ocr_workaround,
                    interactive=True,
                )

                max_pages_per_part = gr.Number(
                    label="Maximum pages per part (for auto-split translation, 0 means no limit)",
                    value=settings.pdf.max_pages_per_part,
                    precision=0,
                    minimum=0,
                    interactive=True,
                )

                formular_font_pattern = gr.Textbox(
                    label="Font pattern to identify formula text (regex, not recommended to change)",
                    value=settings.pdf.formular_font_pattern or "",
                    interactive=True,
                    placeholder="e.g., CMMI|CMR",
                )

                formular_char_pattern = gr.Textbox(
                    label="Character pattern to identify formula text (regex, not recommended to change)",
                    value=settings.pdf.formular_char_pattern or "",
                    interactive=True,
                    placeholder="e.g., [∫∬∭∮∯∰∇∆]",
                )

                ignore_cache = gr.Checkbox(
                    label="Ignore cache",
                    value=settings.translation.ignore_cache,
                    interactive=True,
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
        if not detail_text_inputs:
            return
        detail_group_index = detail_text_input_index_map.get(service_name, [])
        if len(detail_text_inputs) == 1:
            return gr.update(visible=(0 in detail_group_index))
        else:
            return [
                gr.update(visible=(i in detail_group_index))
                for i in range(len(detail_text_inputs))
            ]

    def on_enhance_compatibility_change(enhance_value):
        """Update skip_clean and disable_rich_text_translate when enhance_compatibility changes"""
        if enhance_value:
            # When enhanced compatibility is enabled, both options are auto-enabled and disabled for user modification
            return (
                gr.update(value=True, interactive=False),
                gr.update(value=True, interactive=False),
            )
        else:
            # When disabled, allow user to modify these settings
            return (
                gr.update(interactive=True),
                gr.update(interactive=True),
            )

    def on_split_short_lines_change(split_value):
        """Update short_line_split_factor visibility based on split_short_lines value"""
        return gr.update(visible=split_value)

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
        outputs=detail_text_inputs if len(detail_text_inputs) > 0 else None,
    )

    # Add event handler for enhance_compatibility
    enhance_compatibility.change(
        on_enhance_compatibility_change,
        enhance_compatibility,
        [skip_clean, disable_rich_text_translate],
    )

    # Add event handler for split_short_lines
    split_short_lines.change(
        on_split_short_lines_change,
        split_short_lines,
        short_line_split_factor,
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
            # PDF Output Options
            no_mono,
            no_dual,
            dual_translate_first,
            use_alternating_pages_dual,
            watermark_output_mode,
            # Advanced Options
            prompt,
            threads,
            min_text_length,
            rpc_doclayout,
            custom_system_prompt_input,
            skip_clean,
            disable_rich_text_translate,
            enhance_compatibility,
            split_short_lines,
            short_line_split_factor,
            translate_table_text,
            skip_scanned_detection,
            max_pages_per_part,
            formular_font_pattern,
            formular_char_pattern,
            ignore_cache,
            state,
            ocr_workaround,
            *translation_engine_arg_inputs,
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
    share: bool = False,
    auth_file: list | None = None,
    server_port=7860,
    inbrowser: bool = True,
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
                inbrowser=inbrowser,
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
                    inbrowser=inbrowser,
                    share=share,
                    server_port=server_port,
                )
            except Exception:
                print(
                    "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                )
                demo.launch(
                    debug=True, inbrowser=inbrowser, share=True, server_port=server_port
                )
    else:
        try:
            demo.launch(
                server_name="0.0.0.0",
                debug=True,
                inbrowser=inbrowser,
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
                    inbrowser=inbrowser,
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
                    inbrowser=inbrowser,
                    share=True,
                    auth=user_list,
                    auth_message=html,
                    server_port=server_port,
                )


# For auto-reloading while developing
if __name__ == "__main__":
    from rich.logging import RichHandler

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False
    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])
    setup_gui(inbrowser=False)

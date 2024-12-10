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

def translate(
    file_input,
    service,
    lang_from,
    lang_to,
    page_range,
    *envs,
):

    output = Path("pdf2zh_files")
    output.mkdir(parents=True, exist_ok=True)

    if not file_input:
        raise gr.Error("No input")
    file_path = shutil.copy(file_input, output)
    

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

    param = {
        "files": [file_en],
        "pages": selected_page,
        "lang_in": lang_from,
        "lang_out": lang_to,
        "service": f"{translator.name}",
        "output": output,
        "thread": 4,
    }
    print(param)
    extract_text(**param)
    print(f"Files after translation: {os.listdir(output)}")

    if not file_zh.exists() or not file_dual.exists():
        raise gr.Error("No output")

    return (
        str(file_zh),
        str(file_dual)
    )

demo = gr.Interface(fn=translate,inputs=["text","file"],outputs=["file","file"], api_name="translate")

def setup_interface(share=False):
    demo.launch(server_name="0.0.0.0", debug=True, share=share)


# For auto-reloading while developing
if __name__ == "__main__":
    setup_interface()

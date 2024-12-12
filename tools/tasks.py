from celery import shared_task
from pathlib import Path
from pdf2zh.pdf2zh import translate


@shared_task(ignore_result=False)
def translate_task(
    output_dir: str,
    filename: str,
    lang_in: str = "auto",
    lang_out: str = "zh",
    service: str = "google",
):
    output_dir = Path(output_dir)
    origin_pdf = output_dir / f"{filename}.pdf"
    translated_pdf = output_dir / f"{filename}-zh.pdf"
    dual_pdf = output_dir / f"{filename}-dual.pdf"
    translate(
        files=[str(origin_pdf)],
        lang_in=lang_in,
        lang_out=lang_out,
        service=service,
        thread=4,
        output=str(output_dir)
    )
    return str(translated_pdf), str(dual_pdf)

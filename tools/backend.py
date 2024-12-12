import os
import tempfile

from flask import Flask, request, send_file
from celery import Celery, Task
from celery.result import AsyncResult
from pathlib import Path
from tasks import translate_task


app = Flask("pdf2zh")
app.config.from_mapping(
    CELERY=dict(
        broker_url=os.environ.get("CELERY_BROKER", "redis://127.0.0.1:6379/0"),
        result_backend=os.environ.get("CELERY_RESULT", "redis://127.0.0.1:6379/0"),
        ignore_task_result=False,
    )
)


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.Task = FlaskTask
    celery_app.set_default()
    celery_app.autodiscover_tasks()
    app.extensions["celery"] = celery_app
    return celery_app


celery_app = celery_init_app(app)


@app.route("/api/translate", methods=["POST"])
def create_translate_tasks():
    f = request.files["source"]
    output_dir = Path(tempfile.mkdtemp())
    file_basename = ".".join(f.filename.split(".")[:-1])
    if len(file_basename) == 0:
        file_basename = "input"
    origin_pdf = output_dir / f"{file_basename}.pdf"
    f.save(origin_pdf)
    lang_in = request.args.get("lang_in", "auto")
    lang_out = request.args.get("lang_out", "zh")
    service = request.args.get("service", "google")
    task = translate_task.delay(
        str(output_dir), file_basename, lang_in, lang_out, service
    )
    return {"result_id": task.id}


@app.route("/api/results/<id>", methods=["GET"])
def check_translate_result(id: str):
    result = AsyncResult(id)
    return {"ready": result.ready(), "successful": result.successful()}


@app.route("/api/results/<id>/<format>")
def get_translate_result(id: str, format: str):
    result = celery_app.AsyncResult(id)
    if not result.ready():
        return {"error": "task not finished"}, 400
    if not result.successful():
        return {"error": "task failed"}, 400
    translated_pdf, dual_pdf = result.get()
    to_send = translated_pdf if format == "translated" else dual_pdf
    return send_file(to_send, "application/pdf")


if __name__ == "__main__":
    app.run()

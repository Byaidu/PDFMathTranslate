import os
from flask import Flask, request, send_file
from celery import Celery, Task
from pdf2zh import translate_stream
import tqdm

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


@app.task(bind=True)
def translate_task(
    stream: bytes,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
):
    def progress_bar(t: tqdm.tqdm):
        self.update_state(state="PROGRESS", meta={"n": t.n, "total": t.total})  # noqa
        print(f"Translating {t.n} / {t.total} pages")

    doc_mono, doc_dual = translate_stream(
        stream,
        lang_in=lang_in,
        lang_out=lang_out,
        service=service,
        thread=4,
        callback=progress_bar,
    )
    return doc_mono, doc_dual


@app.route("/api/translate", methods=["POST"])
def create_translate_tasks():
    stream = request.files["file"]
    lang_in = request.args.get("lang_in", "en")
    lang_out = request.args.get("lang_out", "zh")
    service = request.args.get("service", "google")
    task = translate_task.delay(stream, lang_in, lang_out, service)
    return {"id": task.id}


@app.route("/api/results/<id>", methods=["GET"])
def check_translate_result(id: str):
    result = celery_app.AsyncResult(id)
    return {"state": result.state, "info": result.info}


@app.route("/api/results/<id>/<format>")
def get_translate_result(id: str, format: str):
    result = celery_app.AsyncResult(id)
    if not result.ready():
        return {"error": "task not finished"}, 400
    if not result.successful():
        return {"error": "task failed"}, 400
    doc_mono, doc_dual = result.get()
    to_send = doc_mono if format == "mono" else doc_dual
    return send_file(to_send, "application/pdf")


if __name__ == "__main__":
    app.run()

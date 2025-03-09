from fastapi import FastAPI, File, UploadFile, HTTPException,Form
from fastapi.responses import StreamingResponse

import json
import io
from io import BytesIO
import asyncio
from pdf2zh import translate_stream
import tqdm
from pdf2zh.doclayout import ModelInstance
from pdf2zh.config import ConfigManager

import uuid

import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
# 设置日志记录器
logger = logging.getLogger("uvicorn")

# 设置日志记录格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()

console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 禁用 Uvicorn 的日志传播，避免重复配置
logger.propagate = False

# 初始化 FastAPI 应用
app = FastAPI()

# 存储任务状态的简单方式
tasks = {}


# 异步翻译任务函数
async def translate_task(stream: bytes, args: dict):
    """
    异步翻译任务，使用 async/await 来避免阻塞
    """
    # 用于进度条的函数
    def progress_bar(t: tqdm.tqdm):
        task_id = args.get("task_id")
        tasks[task_id]["state"] = "PROGRESS"
        tasks[task_id]["info"] = f"Translating {t.n} / {t.total} pages"
        print(f"Translating {t.n} / {t.total} pages")

    # 执行翻译任务
    doc_mono, doc_dual = translate_stream(
        stream,
        callback=progress_bar,
        model=ModelInstance.value,
        **args,
    )

    tasks[args.get("task_id")]["state"] = "SUCCESS"
    tasks[args.get("task_id")]["result"] = (doc_mono, doc_dual)

@app.get("/")
async def root():
    logger.debug("This is a debug log!")
    return {"message": "Welcome to the PDF Translator API!"}

@app.post("/v1/translate")
async def create_translate_tasks(file: UploadFile = File(...), data: str = Form(...)):
    """
    接收文件并启动翻译任务
    """
    try:
         # 打印请求体内容以调试

        # 输出收到的文件和数据
        logging.debug(f"Received file: {file.filename}")
        logging.debug(f"Received data: {data}")

        if not data:
            raise HTTPException(status_code=400, detail="Missing 'data' field in the request.")
        
        
        # 读取上传文件的内容
        stream = await file.read()

        logging.debug(f"File size: {len(stream)} bytes")
        
        args = json.loads(data)
        logging.info(f"Parsed arguments: {args}")
        
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())  # 使用 UUID 生成唯一的 ID
        tasks[task_id] = {"state": "PENDING", "info": "", "result": None}
        args["task_id"] = task_id
        print(args)

        # 启动异步任务
        asyncio.create_task(translate_task(stream, args))

        logging.debug(f"Task started with ID: {task_id}")
        return {"id": task_id}

    except Exception as e:
        logging.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=f"Error: {e}")



@app.get("/v1/translate/{id}")
async def get_translate_task(id: str):
    """
    获取翻译任务的状态
    """
    task = tasks.get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"state": task["state"], "info": task["info"]}


@app.delete("/v1/translate/{id}")
async def delete_translate_task(id: str):
    """
    删除翻译任务
    """
    task = tasks.get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 终止任务的逻辑可以加在这里
    task["state"] = "CANCELLED"
    return {"state": task["state"]}


@app.get("/v1/translate/{id}/{format}")
async def get_translate_result(id: str, format: str):
    """
    获取翻译结果
    """
    task = tasks.get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["state"] != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task is not finished yet")

    doc_mono, doc_dual = task["result"]
    to_send = doc_mono if format == "mono" else doc_dual
    return StreamingResponse(io.BytesIO(to_send), media_type="application/pdf")

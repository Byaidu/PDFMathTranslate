FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app


EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# Download all required fonts
ADD "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifCN-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifTW-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifJP-Regular.ttf" /app/
ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifKR-Regular.ttf" /app/

RUN apt-get update && \
     apt-get install --no-install-recommends -y libgl1 libglib2.0-dev libxext6 libsm6 libxrender1 && \
     rm -rf /var/lib/apt/lists/* && uv pip install --system --no-cache huggingface-hub && \
     python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('wybxc/DocLayout-YOLO-DocStructBench-onnx','doclayout_yolo_docstructbench_imgsz1024.onnx');"

COPY . .

RUN uv pip install --system --no-cache .

CMD ["pdf2zh", "-i"]

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY . .

EXPOSE 7860

ENV PYTHONUNBUFFERED=1
ADD "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf" /app
RUN apt-get update && \
     apt-get install --no-install-recommends -y libgl1 && \
     rm -rf /var/lib/apt/lists/*

RUN uv pip install --system --no-cache . && uv run pdf2zh/warmup.py

CMD ["pdf2zh", "-i"]
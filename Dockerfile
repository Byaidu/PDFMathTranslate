FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app


EXPOSE 7860

ENV PYTHONUNBUFFERED=1

# # Download all required fonts
# ADD "https://github.com/satbyy/go-noto-universal/releases/download/v7.0/GoNotoKurrent-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifCN-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifTW-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifJP-Regular.ttf" /app/
# ADD "https://github.com/timelic/source-han-serif/releases/download/main/SourceHanSerifKR-Regular.ttf" /app/

RUN apt-get update && \
     apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libxext6 libsm6 libxrender1 && \
     rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml && babeldoc --version && babeldoc --warmup

COPY . .

RUN uv pip install --system --no-cache . && uv pip install --system --no-cache -U "babeldoc<0.3.0" "pymupdf<1.25.3" "pdfminer-six==20250416" && babeldoc --version && babeldoc --warmup

# Create a non-root user for running the application
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/bash -d /app appuser

# Set correct ownership of application files
RUN chown -R appuser:appuser /app

# Switch to non-root user for all subsequent operations
USER appuser

CMD ["pdf2zh", "-i"]

FROM python:3.12

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pdf2zh

CMD ["pdf2zh", "-i"]
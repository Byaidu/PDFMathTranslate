FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN pip install pdf2zh

CMD ["pdf2zh", "-i"]
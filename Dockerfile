FROM python:3.12-slim

WORKDIR /app

RUN pip install pdf2zh

CMD ["pdf2zh", "-i"]
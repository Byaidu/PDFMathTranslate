FROM python:3.12

WORKDIR /app

COPY . .

EXPOSE 7860

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libgl1

RUN pip install .

CMD ["pdf2zh", "-i"]
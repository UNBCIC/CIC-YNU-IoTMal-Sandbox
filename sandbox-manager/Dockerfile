FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./config ./config
COPY ./router ./router
COPY ./service ./service
COPY ./util ./util
COPY ./.env ./main.py ./

RUN mkdir output uploads

ENTRYPOINT ["python3", "main.py"]

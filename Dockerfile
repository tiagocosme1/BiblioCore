FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN mkdir -p /logs

CMD ["python", "servidor.py"]

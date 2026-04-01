FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gerador_dados3.py ./
COPY modules ./modules

# O script escreve em aurorapay_transactions/
RUN mkdir -p /app/aurorapay_transactions

CMD ["python", "gerador_dados3.py"]

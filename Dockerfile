# Use uma imagem base oficial do Python
FROM python:3.12-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código fonte para o diretório de trabalho
COPY gerador_dados3.py .

# Cria o diretório de saída para garantir que ele exista (opcional, pois o script cria)
RUN mkdir -p aurorapay_transactions_delta/raw

# Comando para executar o script quando o container iniciar
CMD ["python", "gerador_dados3.py"]

# Data Generation - AuroraPay Fraud Dataset

Esta pasta documenta o gerador de dados `gerador_dados3.py` e como executar via Docker.

## Objetivo

O script gera dados sintÃ©ticos para cenarios de fraude em pagamentos, exportando:

- `aurorapay_transactions/customer_profiles` (JSON)
- `aurorapay_transactions/merchant_registry` (JSON)
- `aurorapay_transactions/transaction_events` (AVRO)
- `aurorapay_transactions/device_signals` (AVRO)
- `aurorapay_transactions/security_logs` (AVRO)

## Arquivos necessarios

Para rodar o container, esta estrutura precisa existir no repositorio:

```text
Data generation/
  Dockerfile
  requirements.txt
  gerador_dados3.py
  modules/
    __init__.py
    data_utils.py
    merchant_registry.py
```

## Como o gerador funciona (resumo)

- Cria perfis de clientes e comerciantes.
- Simula transacoes legitimas e tipos de fraude (first-party, corporate e traditional).
- Gera sinais de dispositivo com `ip_region` em formato JSON contendo latitude, longitude, acuracia, altitude, timestamp e `region_code`.
- Em `customer_profiles`, gera `card_details` (brand, category, type, virtual, CVV, emissao, expiracao, limites) e `client_details` (genero e idade).
- Injeta problemas de qualidade de dados (nulos, duplicados, ruido e inconsistencias) para simular dados reais.

## Dockerfile recomendado

Use este Dockerfile na pasta `Data generation`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gerador_dados3.py ./
COPY modules ./modules

RUN mkdir -p /app/aurorapay_transactions

CMD ["python", "gerador_dados3.py"]
```

## Build e execucao do container

Na pasta `Data generation`:

```bash
docker build -t aurorapay-data-gen .
docker run --rm -v "${PWD}/aurorapay_transactions:/app/aurorapay_transactions" aurorapay-data-gen
```

No PowerShell (Windows), se preferir caminho absoluto:

```powershell
docker run --rm -v "C:/caminho/para/Data generation/aurorapay_transactions:/app/aurorapay_transactions" aurorapay-data-gen
```

## Publicar na pasta Data generation do GitHub

Repositorio alvo informado:

- `https://github.com/VinicinCanedo/Credit_Fraud_Detection.git`

Passos:

```bash
git clone https://github.com/VinicinCanedo/Credit_Fraud_Detection.git
cd Credit_Fraud_Detection
mkdir -p "Data generation/modules"
```

Copie para dentro de `Data generation/`:

- `Dockerfile`
- `requirements.txt`
- `gerador_dados3.py`
- `modules/__init__.py`
- `modules/data_utils.py`
- `modules/merchant_registry.py`
- `README.md` (este arquivo)

Depois commit e push:

```bash
git add "Data generation"
git commit -m "Add Dockerized data generation pipeline"
git push origin main
```

## Observacao importante

No workspace atual, o remote esta configurado para outro repositorio (`PagSeguro`).
Se quiser enviar diretamente para `Credit_Fraud_Detection`, ajuste o remote ou trabalhe em um clone desse repositorio.

## Fluxo recomendado com Pull Request

Para novas alteracoes, prefira este fluxo:

1. Crie branch de feature a partir da main.
2. Faça commits pequenos e descritivos.
3. Abra PR para main com resumo tecnico e checklist de testes.
4. Faça merge somente apos validacao.

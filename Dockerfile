FROM python:3.11-slim

# Instala ferramentas essenciais do sistema para o agente operar no terminal
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    nano \
    procps \
    iputils-ping \
    tar \
    gzip \
    unzip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Diretório da aplicação
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Cria os diretórios de workspace e storage temporário
RUN mkdir -p /workspace/storage/temp_downloads

# Define variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV WORKSPACE_DIR=/workspace
ENV PORT=8000

EXPOSE 8000

CMD ["python", "main.py"]

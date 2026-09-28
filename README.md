# 🤖 Assistente CLI & DevOps Agent (WhatsApp & Telegram)

Um assistente autônomo com inteligência artificial (**Google Gemini**) conectado ao seu **WhatsApp** (via [Evolution API](https://github.com/EvolutionAPI/evolution-api)) e ao **Telegram**, capaz de executar comandos de terminal, criar e corrigir códigos, gerenciar arquivos, agendar tarefas e enviar e-mails diretamente a partir de mensagens no seu celular.

---

## 🚀 O que o Agente Consegue Fazer?

- 💻 **Executar Comandos de Terminal:** Bash no Linux ou PowerShell no Windows (`npm install`, `docker ps`, `git pull`, etc.).
- 📁 **Manipular Arquivos e Códigos:** Criar pastas, ler scripts existentes, identificar bugs e salvar correções.
- ⏰ **Agendamento de Tarefas:** Agendar ações para daqui a X minutos ou criar rotinas automáticas com expressões Cron.
- ✉️ **Disparo de E-mails:** Enviar e-mails de alerta ou relatórios via SMTP.
- 🧠 **Memória de Conversa:** Lembra das mensagens anteriores para manter o contexto das instruções.

---

## 🛠️ Pré-requisitos & Configuração (.env)

No arquivo `.env`, configure suas credenciais:

```bash
# --- IA (Google Gemini) ---
GEMINI_API_KEY=sua_chave_gemini
GEMINI_MODEL=gemini-2.5-flash

# --- SEGURANÇA & WHITELIST (OBRIGATÓRIO) ---
# Apenas os números ou IDs listados aqui poderão executar ações na máquina.
# WhatsApp: DDI + DDD + Número (ex: 5511999999999)
# Telegram: Seu chat_id numérico (ex: 123456789)
ALLOWED_USERS=5511999999999,123456789

# --- DIRETÓRIO DE TRABALHO ---
WORKSPACE_DIR=./workspace

# --- EVOLUTION API (WHATSAPP) ---
EVOLUTION_API_URL=https://sua-evolution-api.com
EVOLUTION_API_KEY=sua_global_api_key_ou_instance_key
EVOLUTION_INSTANCE_NAME=nome_da_instancia

# --- TELEGRAM BOT (OPCIONAL) ---
TELEGRAM_BOT_TOKEN=seu_token_do_botfather

# --- SMTP / E-MAIL (OPCIONAL) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASS=sua_senha_de_app
SMTP_FROM=seu_email@gmail.com
```

---

## 📦 Como Subir no Easypanel (VPS)

1. No painel do **Easypanel**, clique em **New Project** ou abra seu projeto existente.
2. Adicione um novo **App Service**:
   - **Source:** Selecione **GitHub** (caso tenha subido este código para um repositório) ou selecione **Build from Dockerfile**.
3. Em **Environment Variables**, adicione as variáveis do seu `.env`.
4. Em **Domains**, defina o domínio ou subdomínio público (ex: `assistente.seudominio.com`). O Easypanel gerará automaticamente o certificado HTTPS gratuito (Let's Encrypt).
5. Em **Mounts / Volumes**:
   - Mapeie um volume persistente para `/workspace` para que os arquivos gerados pelo agente não se percam em reinicializações.
   - *(Opcional - Avançado)*: Se quiser que o agente gerencie outros containers do Docker no servidor, mapeie `/var/run/docker.sock` do host para `/var/run/docker.sock` do container.
6. Clique em **Deploy**.

---

## 📲 Conectando com a Evolution API (WhatsApp)

1. Acesse o painel da sua **Evolution API** (Manager ou via requisição de API).
2. Na sua instância conectada ao WhatsApp, vá na aba **Webhooks**:
   - **Webhook URL:** `https://assistente.seudominio.com/webhook/evolution`
   - **Webhook By Events:** Habilite `MESSAGES_UPSERT` (ou marque para escutar todas as mensagens).
   - **Status:** Ativo (`Enabled`).
3. Salve as alterações.
4. Envie uma mensagem pelo WhatsApp a partir do número cadastrado em `ALLOWED_USERS` testando:
   > *"Olá! Liste os arquivos do workspace para mim."*

---

## ✈️ Conectando com o Telegram

1. Crie seu bot no Telegram falando com o `@BotFather` e copie o token gerado.
2. Coloque o token no `.env` em `TELEGRAM_BOT_TOKEN`.
3. Registre o webhook do Telegram abrindo no navegador:
   ```text
   https://api.telegram.org/botSEU_TOKEN_AQUI/setWebhook?url=https://assistente.seudominio.com/webhook/telegram
   ```
4. Para descobrir seu `chat_id` pessoal, mande qualquer mensagem para o bot `@userinfobot` no Telegram e adicione o ID na variável `ALLOWED_USERS`.

---

## 💡 Exemplos de Comandos para Mandar no WhatsApp/Telegram

- **Criar projetos:**
  > *"Crie uma pasta chamada `meu-app` e dentro crie um script Python que faz requisição a uma API de previsão do tempo e salve o resultado em um arquivo json."*

- **Corrigir código:**
  > *"Leia o arquivo `app.py` que está na pasta `meu-app`, encontre onde está ocorrendo erro de divisão por zero e salve a versão corrigida."*

- **Comandos de terminal:**
  > *"Rode `git status` dentro da pasta `projeto-x` e me mostre o que foi alterado."*
  > *"Verifique o uso de memória e disco da VPS com os comandos `free -m` e `df -h`."*

- **Agendamentos:**
  > *"Agende para daqui a 15 minutos verificar se o site https://meusite.com está online e me avise aqui no WhatsApp."*
  > *"Crie uma rotina cron todo dia às 09:00 para listar se há arquivos novos na pasta de uploads."*

- **Limpar memória de conversa:**
  > Envie `/reset` ou `/limpar` para zerar o contexto acumulado no chat.

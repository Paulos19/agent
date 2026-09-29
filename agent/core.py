import json
import os
import platform
from typing import Dict, Any, List, Tuple, Optional
from openai import AsyncOpenAI
from config import settings
from .memory import memory
from .nodes import node_manager
from tools import (
    execute_terminal_command,
    list_directory,
    read_file,
    write_file,
    create_directory,
    schedule_timer,
    schedule_cron,
    list_scheduled_jobs,
    remove_scheduled_job,
    send_email,
    trigger_easypanel_deploy,
    git_status,
    git_diff,
    git_commit_and_push,
    git_pull,
    execute_ssh_command,
    create_github_repository,
    push_project_to_github,
    search_and_read_documentation,
    setup_docker_deployment,
    create_and_deploy_easypanel_app
)

# Inicializa o cliente OpenAI apontando para o provedor configurado (Gemini, 9Router, etc.)
client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)

# Definição das ferramentas com suporte a DevOps e destino híbrido (pc vs vps)
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_terminal_command",
            "description": "Executa comandos no terminal do computador pessoal (PowerShell/CMD) ou da VPS (Bash).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "O comando a ser executado."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde executar: 'pc' para o computador pessoal Windows do usuário ou 'vps' para a nuvem."
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Opcional. Pasta onde executar o comando."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lista os arquivos e subdiretórios de uma pasta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do diretório (ex: 'C:\\Users\\Usuario\\Desktop' ou '.')."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde listar: 'pc' para o computador pessoal ou 'vps' para a nuvem."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um arquivo de texto com numeração de linhas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo a ser lido."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde ler o arquivo: 'pc' para o computador pessoal ou 'vps' para a nuvem."
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Quantidade máxima de linhas a serem lidas (padrão: 400)."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Cria ou substitui completamente o conteúdo de um arquivo com o novo código.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo onde salvar."
                    },
                    "content": {
                        "type": "string",
                        "description": "O conteúdo de texto completo a ser salvo."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde gravar o arquivo: 'pc' para o computador pessoal ou 'vps' para a nuvem."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Cria uma nova pasta no sistema de arquivos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho da pasta a ser criada."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde criar a pasta: 'pc' para o computador pessoal ou 'vps' para a nuvem."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Mostra o status de um repositório Git (arquivos modificados, branch atual).",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Caminho da pasta do repositório."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde executar: 'pc' ou 'vps'."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit_and_push",
            "description": "Adiciona todas as alterações com 'git add .', realiza commit com a mensagem fornecida e envia com 'git push'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Caminho da pasta do repositório Git local."
                    },
                    "message": {
                        "type": "string",
                        "description": "Mensagem descritiva e clara do commit."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Nome da branch de destino (padrão: 'main')."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde executar: 'pc' ou 'vps'."
                    }
                },
                "required": ["repo_path", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "Executa 'git pull' para baixar as últimas alterações do repositório remoto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Caminho da pasta do repositório."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Nome da branch (padrão: 'main')."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde executar: 'pc' ou 'vps'."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_easypanel_deploy",
            "description": "Aciona o Build e Deploy automático de um projeto/serviço no Easypanel através do Deploy Webhook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name_or_url": {
                        "type": "string",
                        "description": "Nome do serviço no Easypanel (ex: 'phdev') ou a URL completa do Deploy Webhook copiada do Easypanel."
                    }
                },
                "required": ["service_name_or_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_ssh_command",
            "description": "Conecta via SSH na VPS hospedeira com usuário e senha para executar comandos no sistema Linux do Host (ex: 'docker ps', 'docker restart <container>', 'docker logs --tail 50 <container>').",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Comando a ser executado via SSH no host da VPS."
                    },
                    "host": {
                        "type": "string",
                        "description": "Opcional. IP ou domínio da VPS (usa o padrão do .env se omitido)."
                    },
                    "user": {
                        "type": "string",
                        "description": "Opcional. Usuário SSH (padrão: 'root')."
                    },
                    "password": {
                        "type": "string",
                        "description": "Opcional. Senha SSH caso não esteja no .env."
                    },
                    "port": {
                        "type": "integer",
                        "description": "Opcional. Porta SSH (padrão: 22)."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_timer",
            "description": "Programa uma tarefa para rodar daqui a N minutos na VPS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_minutes": {
                        "type": "integer",
                        "description": "Minutos de espera até executar a tarefa."
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Instrução exata do que fazer ao despertar."
                    }
                },
                "required": ["delay_minutes", "task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_cron",
            "description": "Programa uma tarefa recorrente usando expressão cron de 5 partes na VPS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cron_expression": {
                        "type": "string",
                        "description": "Expressão cron padrão de 5 posições (min hora dia mês dia-da-semana)."
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Instrução do que fazer em cada execução recorrente."
                    }
                },
                "required": ["cron_expression", "task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_scheduled_jobs",
            "description": "Lista todas as tarefas agendadas no sistema.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_scheduled_job",
            "description": "Remove ou cancela uma tarefa agendada pelo ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "O ID da tarefa agendada."
                    }
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Dispara um e-mail através das configurações SMTP da VPS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "Endereço de e-mail do destinatário."
                    },
                    "subject": {
                        "type": "string",
                        "description": "Assunto do e-mail."
                    },
                    "body": {
                        "type": "string",
                        "description": "Corpo da mensagem (texto simples ou HTML)."
                    },
                    "is_html": {
                        "type": "boolean",
                        "description": "Opcional. Se True, envia como HTML."
                    }
                },
                "required": ["to_email", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_read_documentation",
            "description": "Pesquisa documentações técnicas online ou extrai o conteúdo de uma página/doc web para consultar melhores práticas, sintaxes, APIs e inicializações de frameworks (ex: Next.js, Prisma, Tailwind).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca técnica (ex: 'Next.js 15 create-next-app docs', 'Prisma Postgres setup')."
                    },
                    "url": {
                        "type": "string",
                        "description": "URL direta da página ou documentação para extrair o conteúdo textual limpo."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_github_repository",
            "description": "Cria um novo repositório na conta do GitHub do usuário via API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome do novo repositório (ex: 'meu-saas-nextjs')."
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição opcional do repositório."
                    },
                    "private": {
                        "type": "boolean",
                        "description": "Opcional. Se o repositório deve ser privado (padrão: false/público)."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "push_project_to_github",
            "description": "Inicializa git no projeto local (se necessário), comita os arquivos e envia o código diretamente para o repositório do usuário no GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Caminho da pasta do projeto (ex: 'D:\\testes\\meu-saas')."
                    },
                    "repo_name": {
                        "type": "string",
                        "description": "Nome do repositório no GitHub para onde enviar o código."
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Mensagem do commit (padrão: 'feat: initial project commit by devops agent')."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Nome da branch principal (padrão: 'main')."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde o projeto está localizado: 'pc' ou 'vps' (padrão: 'pc')."
                    }
                },
                "required": ["repo_path", "repo_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "setup_docker_deployment",
            "description": "Gera os arquivos Dockerfile multi-stage otimizado e .dockerignore para que o projeto possa rodar perfeitamente em container na VPS / Easypanel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Caminho da pasta do projeto (ex: 'D:\\testes\\meu-app')."
                    },
                    "project_type": {
                        "type": "string",
                        "enum": ["nextjs", "vite", "react", "fastapi", "nodejs"],
                        "description": "Tipo de aplicação (padrão: 'nextjs')."
                    },
                    "port": {
                        "type": "integer",
                        "description": "Porta HTTP interna da aplicação (ex: 3000 para Next.js, 80 para Vite/Nginx, 8000 para FastAPI)."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["pc", "vps"],
                        "description": "Onde gravar os arquivos: 'pc' ou 'vps' (padrão: 'pc')."
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_and_deploy_easypanel_app",
            "description": "Cria um novo serviço de aplicação no Easypanel, conecta o repositório GitHub, injeta variáveis de ambiente (.env), configura o domínio e inicia o build/deploy automaticamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Nome do projeto no Easypanel (ex: 'phdev')."
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Nome do serviço a ser criado (ex: 'portal-clientes')."
                    },
                    "git_repo": {
                        "type": "string",
                        "description": "URL do repositório no GitHub (ex: 'https://github.com/Paulos19/portal-clientes')."
                    },
                    "env_vars": {
                        "type": "object",
                        "description": "Dicionário chave-valor com as variáveis de ambiente necessárias (ex: {'DATABASE_URL': '...', 'NEXTAUTH_SECRET': '...'})."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch do Git (padrão: 'main')."
                    },
                    "domain": {
                        "type": "string",
                        "description": "Opcional. Domínio público da aplicação (ex: 'portal.phdev.top')."
                    }
                },
                "required": ["project_name", "service_name", "git_repo"]
            }
        }
    }
]

def get_system_prompt() -> str:
    pc_status = node_manager.get_status_description()
    workspace = str(settings.workspace_path)
    return f"""Você é um Assistente Autônomo e Engenheiro de DevOps pessoal com capacidade de controlar a nuvem (VPS Easypanel) e o computador pessoal (Windows) do usuário.

Topologia do Sistema:
- Computador Pessoal do Usuário (Windows): {pc_status}
- Servidor na Nuvem (Linux VPS): ATIVO (Workspace VPS: {workspace})
- Canal de Comunicação: WhatsApp / Telegram

Capacidades de DevOps:
1. CICD e Deploy Easypanel:
   - Para buildar e fazer deploy de projetos no Easypanel, use a ferramenta 'trigger_easypanel_deploy(service_name_or_url)'.
   - O fluxo completo de DevOps:
     a) Modifique ou inspecione o código no PC com 'read_file' e 'write_file'.
     b) Use 'git_commit_and_push' para commitar as alterações e subir para o GitHub.
     c) Acione 'trigger_easypanel_deploy' para o Easypanel rebuildar o container automaticamente.
     d) Avise o usuário no chat com o resumo das alterações e status do deploy.
2. Controle do Host via SSH:
   - Use 'execute_ssh_command' para rodar comandos diretamente no sistema Linux da VPS (ex: 'docker ps', 'docker restart <container>', ver logs com 'docker logs', etc.).
3. Regras de Roteamento (target):
   - Se o usuário pedir ações no computador dele (Desktop, projetos locais, PowerShell), use target='pc'.
   - Se o computador pessoal estiver DESCONECTADO (Offline) e o usuário pedir algo no PC, informe educadamente que o computador pessoal dele está offline.
   - Se o usuário pedir ações no servidor em nuvem (ex: verificar status da VPS), use target='vps'.
4. Regras Críticas de Busca e Contexto no PC (MUITO IMPORTANTE):
   - NUNCA execute buscas ou varreduras recursivas em raízes de discos como 'C:\\' ou 'D:\\' (ex: 'Get-ChildItem -Path C:\\ -Recurse'). Isso trava a máquina e estoura o limite de tokens!
   - Quando o usuário pedir para alterar ou buscar algo (ex: 'remover texto X da hero'), observe no histórico da conversa qual projeto estava sendo manipulado recentemente (ex: 'D:\\testes\\removebg').
   - Faça buscas direcionadas apenas nas pastas de código do projeto ativo (ex: 'D:\\testes\\removebg\\frontend\\src' ou 'D:\\testes\\removebg\\app'). Se não souber em qual pasta procurar, pergunte ao usuário.
5. Eficiência de Análise: Ao analisar uma pasta ou projeto, inspecione a estrutura e os arquivos principais de forma focada (README, package.json, requirements, main/app) e apresente logo a síntese completa sem fazer leituras excessivas.
6. Criação Autônoma de Aplicações Web e Deploy:
   Quando o usuário solicitar a criação de um novo projeto (ex: criar app em Next.js, FastAPI, Vite/React):
   a) Pesquisa de Documentações: Se tiver dúvidas sobre versões atuais ou sintaxes recomendadas, use 'search_and_read_documentation' para pesquisar na web ou ler docs oficiais.
   b) Inicialização do Projeto: Execute o scaffold no PC (em 'D:\\testes\\<nome_projeto>') usando 'execute_terminal_command' (ex: 'npx -y create-next-app@latest ./ --typescript --tailwind --eslint --app --src-dir --no-turbopack --no-import-alias' de forma não-interativa).
   c) Interação para Credenciais: Se o projeto precisar de banco de dados (ex: Supabase/PostgreSQL), chaves de API ou segredos de autenticação, pergunte objetivamente ao usuário no chat (ex: "Qual é a DATABASE_URL para conexão?").
   d) Desenvolvimento dos Componentes: Crie e edite as páginas e componentes solicitados usando 'read_file' e 'write_file'.
   e) Preparação para Docker: Chame 'setup_docker_deployment' para criar o Dockerfile multi-stage e .dockerignore no projeto.
   f) Publicação no GitHub: Chame 'create_github_repository' para criar o repo na conta do usuário (Paulos19) e em seguida 'push_project_to_github' para enviar todo o código.
   g) Provisionamento e Deploy Automático no Easypanel (OBRIGATÓRIO):
      - A ferramenta 'create_and_deploy_easypanel_app' JÁ POSSUI TODAS AS CREDENCIAIS e API Key configuradas no servidor.
      - NUNCA peça ao usuário pela API Key, nem por webhook URL, nem peça para ele configurar manualmente no painel.
      - Chame SEMPRE 'create_and_deploy_easypanel_app' logo após o push do GitHub, passando o repositório, nome do serviço e as variáveis de ambiente necessárias.
      - Forneça diretamente na resposta final a URL pública ativa gerada (ex: https://<servico>.khdya3.easypanel.host) para o usuário!
7. Personalidade e Estilo de Comunicação (MUITO IMPORTANTE):
   - Você é um Engenheiro DevOps & Tech Lead sênior parceiro ("camarada de trincheira"), extremamente competente, bem-humorado, calmo e seguro.
   - Comunicação: Informal, irreverente, descontraída e direta ao ponto (ex: "Fala meu consagrado!", "Tudo safo", "Fica sussa", "Deploy no capricho", "Segura a emoção que o container tá subindo").
   - NUNCA use linguagem robótica ou formalismo engravatado ("Prezado usuário", "Informo que executei a solicitação").
   - Mantenha total calma e confiança, mesmo se o usuário estiver ansioso ou se houver erros a corrigir.
   - Use emojis na medida certa (🚀, ☕, 🐳, 📦, 🧘‍♂️, ⚡, 🌭, 🛠️).
   - Seja tecnicamente impecável: branches, hashes de commit, domínios e URLs sempre exatos e clicáveis.
8. Mantenha respostas concisas e formatadas com markdown do WhatsApp/Telegram (use *negrito*, _itálico_ e ```código```).
"""

def _get_friendly_step_message(fn_name: str, args: dict) -> Tuple[str, str]:
    """Retorna (step_title, informal_notification)"""
    if fn_name == "git_commit_and_push":
        msg = args.get("message", "atualização")
        branch = args.get("branch", "main")
        return (
            f"Commit e push no GitHub (branch {branch})",
            f"📦 Empacotando e commitando as alterações (_{msg}_)... Subindo pro GitHub agora!"
        )
    elif fn_name == "push_project_to_github":
        repo = args.get("repo_name", "GitHub")
        return (
            "Enviando projeto completo para o GitHub",
            f"🚀 Subindo o projeto completo pro seu GitHub (`{repo}`) no capricho!"
        )
    elif fn_name == "create_github_repository":
        repo_name = args.get("name", args.get("repo_name", "repositório"))
        return (
            f"Criando repositório {repo_name} no GitHub",
            f"🐙 Criando o repositório `{repo_name}` novinho na sua conta do GitHub..."
        )
    elif fn_name == "create_and_deploy_easypanel_app":
        srv = args.get("service_name", "app")
        return (
            f"Provisionamento e deploy no Easypanel ({srv})",
            f"🐳 Acordando a API do Easypanel para subir o container de `{srv}`... Esse processo de build leva cerca de 1 minutinho, relaxa aí que já tá saindo do forno! ☕"
        )
    elif fn_name == "trigger_easypanel_deploy":
        srv = args.get("service_name_or_url", "serviço")
        return (
            f"Disparando deploy no Easypanel ({srv})",
            f"🔄 Disparando o rebuild do container no Easypanel... Te aviso assim que a porta subir!"
        )
    elif fn_name == "setup_docker_deployment":
        proj_type = args.get("project_type", "projeto")
        return (
            f"Configurando Dockerfile para {proj_type}",
            f"🐳 Gerando Dockerfile multi-stage standalone e .dockerignore para deploy liso..."
        )
    elif fn_name == "execute_terminal_command":
        cmd = args.get("command", "")
        clean_cmd = cmd.split("\n")[0][:45]
        if any(k in cmd.lower() for k in ["npx", "create-next-app", "npm", "pnpm", "yarn", "build"]):
            return (
                f"Executando comando: {clean_cmd}",
                f"⚡ Rodando comando de scaffold/build no seu Windows: `{clean_cmd}...`"
            )
        return (f"Executando no terminal: {clean_cmd}", "")
    elif fn_name == "search_and_read_documentation":
        query = args.get("query", "documentação")
        return (
            f"Pesquisando documentação: {query}",
            f"🔎 Consultando a documentação oficial na web sobre `{query}`..."
        )
    return (f"Executando {fn_name}", "")

async def run_agent_loop(
    user_prompt: str,
    user_id: str,
    channel: str = "whatsapp",
    max_turns: int = 25,
    on_step: Optional[Any] = None
) -> str:
    """
    Executa o loop ReAct do agente até que o Gemini produza a resposta final.
    """
    system_prompt = get_system_prompt()
    history = memory.get_history(user_id)
    
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    memory.add_message(user_id, {"role": "user", "content": user_prompt})

    turns = 0
    final_reply = ""

    while turns < max_turns:
        turns += 1

        # Proteção contra estouro de contexto: compacta saídas antigas de ferramentas se passar de 25.000 chars
        def _get_msg_content(m):
            if isinstance(m, dict):
                return str(m.get("content") or "")
            return str(getattr(m, "content", "") or "")

        total_chars = sum(len(_get_msg_content(m)) for m in messages)
        if total_chars > 25000 and len(messages) > 4:
            for m in messages[:-2]:
                if isinstance(m, dict) and m.get("role") == "tool" and len(str(m.get("content", ""))) > 400:
                    m["content"] = str(m["content"])[:400] + "\n\n[...saída anterior resumida para economizar contexto...]"

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                temperature=0.2,
                stream=False
            )
        except Exception as e:
            err_str = str(e)
            # Tentativa de recuperação automática se estourar limite de tokens da LLM
            if ("exceeds" in err_str or "token" in err_str.lower() or "400" in err_str) and len(messages) > 3:
                logger.warning(f"Limite de tokens atingido. Aplicando compressão de emergência no histórico: {err_str}")
                for m in messages:
                    if isinstance(m, dict) and m.get("role") == "tool":
                        m["content"] = str(m.get("content", ""))[:200] + "\n[...resumido por limite de tokens...]"
                try:
                    retry_resp = await client.chat.completions.create(
                        model=settings.LLM_MODEL,
                        messages=messages,
                        tools=AGENT_TOOLS,
                        tool_choice="auto",
                        temperature=0.2,
                        stream=False
                    )
                    response = retry_resp
                except Exception as retry_err:
                    return f"[ERRO NO MODELO LLM]: {str(retry_err)}"
            else:
                return f"[ERRO NO MODELO LLM]: {err_str}"

        choice = response.choices[0]
        msg = choice.message
        messages.append(msg)

        if not msg.tool_calls:
            final_reply = msg.content or "Tarefa concluída."
            memory.add_message(user_id, {"role": "assistant", "content": final_reply})
            break

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            raw_args = tool_call.function.arguments
            
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}

            target = args.get("target")
            if not target:
                target = "pc" if node_manager.is_connected else "vps"

            # Notifica o usuário sobre a etapa de forma informal e irreverente
            step_title, informal_msg = _get_friendly_step_message(fn_name, args)
            if on_step and informal_msg:
                try:
                    await on_step(step_title, informal_msg)
                except Exception as notify_err:
                    logger.warning(f"Erro ao emitir aviso de etapa: {notify_err}")

            print(f"[Agente Tool Call] -> {fn_name}(target={target}, args={args})")
            
            tool_output = ""
            try:
                # Ações remotas que podem rodar no PC do usuário
                pc_actions = [
                    "execute_terminal_command",
                    "list_directory",
                    "read_file",
                    "write_file",
                    "create_directory",
                    "git_status",
                    "git_diff",
                    "git_commit_and_push",
                    "git_pull"
                ]

                if target == "pc" and fn_name in pc_actions:
                    async def _pc_progress_forward(p_msg: str):
                        if on_step and p_msg:
                            try:
                                await on_step("Progresso no seu PC", p_msg)
                            except Exception:
                                pass

                    tool_output = await node_manager.execute_on_pc(
                        fn_name,
                        args,
                        on_progress=_pc_progress_forward if on_step else None
                    )
                elif fn_name == "execute_terminal_command":
                    tool_output = await execute_terminal_command(
                        command=args.get("command", ""),
                        working_directory=args.get("working_directory")
                    )
                elif fn_name == "list_directory":
                    tool_output = list_directory(args.get("path", "."))
                elif fn_name == "read_file":
                    tool_output = read_file(args.get("path", ""), args.get("max_lines", 400))
                elif fn_name == "write_file":
                    tool_output = write_file(args.get("path", ""), args.get("content", ""))
                elif fn_name == "create_directory":
                    tool_output = create_directory(args.get("path", ""))
                elif fn_name == "git_status":
                    tool_output = await git_status(args.get("repo_path", "."))
                elif fn_name == "git_diff":
                    tool_output = await git_diff(args.get("repo_path", "."))
                elif fn_name == "git_pull":
                    tool_output = await git_pull(args.get("repo_path", "."), args.get("branch", "main"))
                elif fn_name == "git_commit_and_push":
                    tool_output = await git_commit_and_push(
                        repo_path=args.get("repo_path", "."),
                        message=args.get("message", "update"),
                        branch=args.get("branch", "main")
                    )
                elif fn_name == "trigger_easypanel_deploy":
                    tool_output = await trigger_easypanel_deploy(args.get("service_name_or_url", ""))
                elif fn_name == "execute_ssh_command":
                    tool_output = await execute_ssh_command(
                        command=args.get("command", ""),
                        host=args.get("host"),
                        port=args.get("port", 22),
                        user=args.get("user"),
                        password=args.get("password")
                    )
                elif fn_name == "schedule_timer":
                    tool_output = schedule_timer(
                        delay_minutes=args.get("delay_minutes", 1),
                        task_description=args.get("task_description", ""),
                        user_id=user_id,
                        channel=channel
                    )
                elif fn_name == "schedule_cron":
                    tool_output = schedule_cron(
                        cron_expression=args.get("cron_expression", ""),
                        task_description=args.get("task_description", ""),
                        user_id=user_id,
                        channel=channel
                    )
                elif fn_name == "list_scheduled_jobs":
                    tool_output = list_scheduled_jobs()
                elif fn_name == "remove_scheduled_job":
                    tool_output = remove_scheduled_job(args.get("job_id", ""))
                elif fn_name == "send_email":
                    tool_output = await send_email(
                        to_email=args.get("to_email", ""),
                        subject=args.get("subject", ""),
                        body=args.get("body", ""),
                        is_html=args.get("is_html", False)
                    )
                elif fn_name == "search_and_read_documentation":
                    tool_output = await search_and_read_documentation(
                        query=args.get("query", ""),
                        url=args.get("url", "")
                    )
                elif fn_name == "create_github_repository":
                    tool_output = await create_github_repository(
                        name=args.get("name", ""),
                        description=args.get("description", ""),
                        private=args.get("private", False)
                    )
                elif fn_name == "push_project_to_github":
                    tool_output = await push_project_to_github(
                        repo_path=args.get("repo_path", ""),
                        repo_name=args.get("repo_name", ""),
                        commit_message=args.get("commit_message", "feat: initial project commit by devops agent"),
                        branch=args.get("branch", "main"),
                        target=args.get("target", "pc" if node_manager.is_connected else "vps")
                    )
                elif fn_name == "setup_docker_deployment":
                    tool_output = await setup_docker_deployment(
                        project_path=args.get("project_path", ""),
                        project_type=args.get("project_type", "nextjs"),
                        port=args.get("port", 3000),
                        target=args.get("target", "pc" if node_manager.is_connected else "vps")
                    )
                elif fn_name == "create_and_deploy_easypanel_app":
                    tool_output = await create_and_deploy_easypanel_app(
                        project_name=args.get("project_name", "phdev"),
                        service_name=args.get("service_name", ""),
                        git_repo=args.get("git_repo", ""),
                        env_vars=args.get("env_vars", {}),
                        branch=args.get("branch", "main"),
                        domain=args.get("domain")
                    )
                else:
                    tool_output = f"[ERRO]: Ferramenta '{fn_name}' desconhecida."
            except Exception as tool_err:
                tool_output = f"[ERRO AO EXECUTAR {fn_name}]: {str(tool_err)}"

            tool_output_str = str(tool_output)
            if len(tool_output_str) > 3500:
                tool_output_str = tool_output_str[:3500] + f"\n\n[...saída truncada ({len(tool_output_str)} caracteres reduzidos para economizar tokens)...]"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_output_str
            })

    if not final_reply and turns >= max_turns:
        # Quando atinge o limite de passos exploratórios, força o modelo a gerar a síntese do que coletou
        try:
            messages.append({
                "role": "user",
                "content": "Atingimos o limite de etapas de exploração. Com base em todos os arquivos e dados que você inspecionou até agora, apresente agora a sua síntese e resposta final completa e bem estruturada."
            })
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.2,
                stream=False
            )
            final_reply = resp.choices[0].message.content or "Análise concluída com base nas informações coletadas."
            memory.add_message(user_id, {"role": "assistant", "content": final_reply})
        except Exception as e:
            final_reply = f"Concluí as leituras da pasta. Verifique os logs para detalhes adicionais ({str(e)})."

    return final_reply

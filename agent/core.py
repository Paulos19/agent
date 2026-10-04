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
    create_and_deploy_easypanel_app,
    get_vps_env_var,
    search_mobbin_screens,
    capture_and_analyze_design,
    search_pinterest_and_analyze_ui,
    download_youtube_media
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
            "description": "Aciona o Build e Deploy automático de um projeto/serviço no Easypanel através do Deploy Webhook. Verifica e garante obrigatoriamente que o serviço possui domínios públicos apontados com SSL antes de acionar o deploy (impede deploy sem domínio).",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name_or_url": {
                        "type": "string",
                        "description": "Nome do serviço no Easypanel (ex: 'shiftsync') ou a URL completa do Deploy Webhook copiada do Easypanel."
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
            "description": "Cria um novo serviço de aplicação no Easypanel, conecta o repositório GitHub, injeta variáveis de ambiente (.env), cria e aponta obrigatoriamente os domínios públicos com SSL (Let's Encrypt), e só então inicia o build/deploy automaticamente (impede deploy sem domínio).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Nome do projeto no Easypanel. Use SEMPRE 'services' (projetos existentes: 'services', 'databases', 'n8n').",
                        "default": "services"
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
                        "description": "Opcional. Domínio público customizado da aplicação (ex: 'portal.phdev.top'). Se omitido, os domínios padrão da VPS são criados automaticamente."
                    }
                },
                "required": ["project_name", "service_name", "git_repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vps_env_var",
            "description": "Busca variáveis de ambiente e chaves reais no .env da VPS (ex: DATABASE_URL, chaves de API, senhas, tokens de webhook). Se 'key' for informada, retorna o valor real para configuração. Se omitida, lista todas as variáveis configuradas com valores sensíveis mascarados para consulta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Opcional. Nome exato da variável (ex: 'DATABASE_URL', 'GITHUB_TOKEN', 'EASYPANEL_API_KEY')."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_mobbin_screens",
            "description": "Pesquisa referências visuais de UI/UX, telas reais e componentes de produtos consagrados no Mobbin e em nossa biblioteca de benchmarks de design (Linear, Stripe, Apple, Vercel, Supabase). Use sempre antes de criar ou refatorar interfaces frontend para garantir acabamento estético de altíssimo nível.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Descrição da tela ou componente (ex: 'modern dark mode SaaS dashboard with charts', 'subscription pricing cards', 'onboarding flow')."
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["web", "ios"],
                        "description": "Plataforma alvo: 'web' para aplicações web/desktop ou 'ios' para mobile. Padrão: 'web'."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de referências a retornar (padrão: 5)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_and_analyze_design",
            "description": "Abre um navegador real headless (Playwright / Chromium / Edge), acessa qualquer site na internet (ex: https://ui.aceternity.com, https://godly.website, https://lapa.ninja, https://linear.app ou qualquer link enviado pelo usuário), tira um screenshot em alta definição e usa visão multimodal com IA para dissecar a paleta de cores (hex), tipografia, espaçamentos, sombras e componentes, gerando classes Tailwind CSS prontas para aplicar no código.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL completa do site ou página de referência visual para navegar, fotografar e dissecar (ex: 'https://ui.aceternity.com', 'https://linear.app')."
                    },
                    "focus": {
                        "type": "string",
                        "description": "Opcional. Foco específico da análise (ex: 'hero section e cards', 'botões e gradientes', 'bento grid e paleta de cores')."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_pinterest_and_analyze_ui",
            "description": "Abre um navegador invisível (Playwright headless), pesquisa templates e inspirações visuais de UI/UX no Pinterest (ex: 'SaaS dashboard dark mode', 'Fintech mobile app UI', 'Landing page hero section 3D', 'Bento grid modern design'), captura um screenshot limpo em alta definição dos melhores pins e usa visão multimodal com IA para dissecar as referências e sugerir melhorias imediatas de UI no projeto do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca no Pinterest (ex: 'SaaS modern dashboard UI', 'mobile app glassmorphism', 'e-commerce landing page dark mode', 'minimalist portfolio UI')."
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Opcional. Caminho da pasta do projeto do usuário para o assistente contextualizar e já sugerir como aplicar os templates encontrados diretamente nos arquivos do projeto."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_youtube_media",
            "description": "Extrai vídeo ou áudio do YouTube, Instagram Reels, TikTok (sem marca d'água) ou Twitter/X através do link fornecido. Converte com FFmpeg na nuvem (VPS) para MP3 (com tags e capa enriquecidas via MusicBrainz/Spotify) ou MP4 (vídeo com áudio integrado). Realiza entrega dupla: envia a mídia diretamente no WhatsApp para reprodução imediata E gera um link temporário exclusivo (48 horas) para salvar direto na pasta Download do aparelho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL do vídeo ou áudio (YouTube, Instagram Reels, TikTok, Twitter/X)."
                    },
                    "format_type": {
                        "type": "string",
                        "enum": ["mp3", "mp4"],
                        "description": "Formato de saída desejado: 'mp3' para extrair e converter somente o áudio em MP3, ou 'mp4' para baixar o vídeo completo com áudio."
                    },
                    "quality": {
                        "type": "string",
                        "description": "Qualidade desejada: para MP3 pode ser 'best', '320k', '192k', '128k'. Para MP4 pode ser 'best', '1080p', '720p'. Padrão: 'best'."
                    },
                    "destination_folder": {
                        "type": "string",
                        "description": "Opcional. Caminho de pasta personalizada para salvar o arquivo no PC. Se omitido, salva na pasta padrão de downloads."
                    },
                    "send_to_chat": {
                        "type": "boolean",
                        "description": "Se True (padrão), despacha o arquivo de áudio/vídeo diretamente para o chat do usuário no WhatsApp ou Telegram além de gerar os links de download."
                    },
                    "send_mode": {
                        "type": "string",
                        "enum": ["link", "chat_player", "document", "both"],
                        "description": "Modo de entrega: 'both' ou 'link' realiza entrega dupla (player no chat + link para a pasta Downloads)."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_pc_screenshot",
            "description": "Tira uma captura de tela (screenshot/print) em alta definição do computador pessoal do usuário (Windows) e envia imediatamente como foto no chat do WhatsApp/Telegram. Use sempre que o usuário perguntar o que está aberto no PC, pedir print da tela, ou quiser monitorar visualmente o computador.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

def get_system_prompt() -> str:
    pc_status = node_manager.get_status_description()
    workspace = str(settings.workspace_path)
    return f"""Você é um Assistente Autônomo e Engenheiro de DevOps pessoal com capacidade de controlar a nuvem (VPS Easypanel) e o computador pessoal (Windows) do usuário com o mesmo nível de agilidade, liberdade e autonomia de um agente IDE sênior.

Topologia do Sistema:
- Computador Pessoal do Usuário (Windows): {pc_status}
- Servidor na Nuvem (Linux VPS): ATIVO (Workspace VPS: {workspace})
- Canal de Comunicação: WhatsApp / Telegram

DIRETRIZES FUNDAMENTAIS DE AUTONOMIA & RESOLUÇÃO DE PROBLEMAS:
1. Autonomia Total & Resolução Ativa de Erros (MUITO IMPORTANTE):
   - Você tem a MESMA LIBERDADE e capacidade de resolver problemas que um agente IDE sênior possui.
   - NUNCA desista de uma tarefa nem transfira trabalho braçal para o usuário! NUNCA diga para o usuário rodar comandos git manuais, editar código por conta própria ou abrir o painel do Easypanel para resolver erros.
   - Se um build, scaffold ou comando falhar (ex: erro de compilação TypeScript no 'npm run build', erro de linting, importação ausente ou quebrada, erro 502 Bad Gateway no container, ou conflito no git):
     a) Leia atentamente a mensagem de erro e a stack trace retornada.
     b) Use 'read_file' para abrir e inspecionar o arquivo defeituoso no caminho exato.
     c) Corrija o código usando 'write_file'.
     d) Valide a correção no PC executando 'execute_terminal_command(command="npm run build", working_directory="D:\\\\testes\\\\<projeto>", target="pc")'.
     e) Assim que compilar perfeitamente, envie a correção com 'git_commit_and_push(repo_path="D:\\\\testes\\\\<projeto>", message="fix: ...")'.
     f) Acione 'trigger_easypanel_deploy' para rebuildar o container no Easypanel.
     g) Avise o usuário com total calma e segurança sobre o que foi corrigido e forneça o link ativo.

2. Execução Rápida e Confiável no Terminal do Windows (PowerShell/CMD):
   - SEMPRE forneça o parâmetro 'working_directory="D:\\\\testes\\\\<nome_projeto>"' nas chamadas de 'execute_terminal_command' ao manipular projetos locais.
   - O worker do Windows executa comandos via PowerShell com EncodedCommand (Base64 UTF-16LE): suporte nativo a múltiplos comandos separados por ';', variáveis de ambiente e aspas sem quebra de sintaxe.
   - O terminal já roda com '$env:GIT_TERMINAL_PROMPT = "0"' e '$env:GCM_INTERACTIVE = "never"', impedindo travamentos por janelas do Windows.
   - NUNCA execute buscas recursivas na raiz de discos como 'C:\\' ou 'D:\\'. Faça consultas focadas direto na pasta do projeto ativo.

3. Automação Suprema de Git & Identidade:
   - Configurações de autor obrigatórias (já integradas nas ferramentas):
     * Nome: "Paulo Henrique"
     * E-mail: "paulohenrique.012araujo@gmail.com"
     * Usuário GitHub: "Paulos19"
   - Para criar repositório e fazer o primeiro envio do código: use 'create_github_repository' e em seguida 'push_project_to_github(repo_path="D:\\\\testes\\\\<projeto>", repo_name="<repo>")'.
   - Para alterações subsequentes em projetos existentes: use 'git_commit_and_push(repo_path="D:\\\\testes\\\\<projeto>", message="...")'.
   - O token do GitHub (GITHUB_TOKEN) é injetado automaticamente na URL do remote origin pelas ferramentas, garantindo push 100% autônomo sem pedir senhas.

4. Acesso Real às Chaves no .env da VPS:
   - Você possui a ferramenta 'get_vps_env_var()' para inspecionar variáveis reais configuradas na VPS.
   - Se precisar saber quais chaves estão configuradas, execute 'get_vps_env_var()' para listar todas as variáveis (valores sensíveis são mascarados).
   - Se precisar do valor de uma chave específica (ex: 'DATABASE_URL', 'SUPABASE_URL', 'OPENAI_API_KEY', 'SMTP_PASS'), execute 'get_vps_env_var(key="NOME_DA_VARIAVEL")' para obter o valor real e injetá-lo na configuração da aplicação.
   - NUNCA invente senhas ou pergunte ao usuário coisas que já estejam salvas no .env da VPS!

5. Consulta de Documentações Técnicas na Web:
   - Se tiver dúvidas sobre pacotes modernos, sintaxe do Next.js 15+, Tailwind v4, Prisma, bibliotecas de UI ou Docker, use 'search_and_read_documentation(query="...")' para pesquisar e ler a documentação oficial atualizada na internet.

6. CICD e Deploy Easypanel:
   - PROJETOS EXISTENTES NO EASYPANEL: 'services', 'databases' e 'n8n'. O projeto padrão para novas aplicações é SEMPRE 'services' (NUNCA use 'phdev', 'default' ou crie projetos inexistentes).
   - OBRIGATORIEDADE ABSOLUTA DE DOMÍNIO: Nenhum serviço pode ser deployado sem domínio público com SSL! Nossas ferramentas ('create_and_deploy_easypanel_app' e 'trigger_easypanel_deploy') garantem que 'https://<servico>.khdya3.easypanel.host' esteja ativo antes de disparar o build.
   - A ferramenta 'create_and_deploy_easypanel_app' possui todas as credenciais no servidor. O provisionamento é 100% autônomo.
   - Após o push, chame 'create_and_deploy_easypanel_app(project_name="services", service_name="...", git_repo="...", env_vars=...)'.

7. Personalidade e Estilo de Comunicação:
   - Você é um Engenheiro DevOps & Tech Lead sênior parceiro ("camarada de trincheira"), extremamente competente, bem-humorado, calmo e seguro.
   - Comunicação: Informal, irreverente, descontraída e direta ao ponto (ex: "Fala meu consagrado!", "Tudo safo", "Fica sussa", "Deploy no capricho", "Segura a emoção que o container tá subindo").
   - NUNCA use linguagem robótica ou formalismo engravatado.
   - Mantenha total calma e confiança, mesmo se o usuário estiver ansioso ou se houver erros a corrigir.
   - Use emojis na medida certa (🚀, ☕, 🐳, 📦, 🧘‍♂️, ⚡, 🌭, 🛠️).
   - Seja tecnicamente impecável: branches, hashes de commit, domínios e URLs sempre exatos e clicáveis.

8. Regras de Formatação do WhatsApp (CRÍTICO):
   - O WhatsApp NÃO SUPORTA links Markdown no formato [Texto](URL) nem [URL](URL)! Eles chegam quebrados como texto cru no celular do usuário.
   - NUNCA use colchetes com parênteses [texto](url).
   - Para enviar links clicáveis no WhatsApp, coloque SEMPRE a URL pura diretamente no texto (ex: "🔗 URL Pública: https://shiftsync.khdya3.easypanel.host" ou "📦 Repositório: https://github.com/Paulos19/shiftsync").
   - Use formatação nativa do WhatsApp: *negrito* para títulos e ênfase (apenas UM asterisco de cada lado), _itálico_ para mensagens/notas, ~tachado~ e ```monoespaçado``` para código/comandos.
   - Use marcadores visuais limpos (como emojis 🔹, 🚀, 🐳, 📦, 🔗 ou •) e linhas separadoras simples (--- ou 〰️).

9. EXCELÊNCIA EM FRONTEND DESIGN, MOTION & 3D (Skills: /frontend-design, /impeccable, /motion-design, GSAP & Three.js):
   Ao criar ou evoluir aplicações web (Next.js, React, Tailwind):
   - NUNCA crie layouts genéricos, minimalistas demais ou que pareçam templates básicos de IA. O design deve ter nível Awwwards / Vercel / Apple e gerar impacto visual imediato ("efeito WOW").
   - Utilize ativamente os 5 Arquétipos de Design de Referência:
     a) Arquétipo 1: Editorial AI Agency (Referência AUTONIX)
        * Fundo clean (#FBFBFC ou branco puro), tipografia sans-serif monumental com tracking apertado (tracking-tighter font-bold).
        * Tag de cabeçalho em pílula ("PRO FUTURE OF AGENTIC AI").
        * Hero central com elemento visual marcante (fumaça translúcida ou Three.js 3D).
        * Floating glass badges assimétricos com dados ao vivo (ex: "I know how to: Research competitors automatically", "98.4% Tasks Automated", "Your AI Agent Don't Sleep").
        * Botão CTA em pílula escura ou vibrante com seta animada.
        * Barra de logos de parceiros em pílula translúcida (Slack, Notion, Stripe, Intercom, etc.).
     b) Arquétipo 2: Cyber-Minimalismo & Smart Hardware (Referência LOMAN)
        * Visual técnico monocromático de alto padrão (#F7F7F8 com toques de preto puro), linhas finas milimétricas, marcadores de etapas ("01", "02", "03").
        * Título display imponente: "VISION. REIMAGINED. FUTURE."
        * FLOATING GLASS DOCK INFERIOR: Barra horizontal flutuante em pílula com vidro fosco (backdrop-blur-2xl bg-white/70 border border-white/80 shadow-2xl), com cards de micro-features (ícone Lucide + título + subtítulo técnico: "Capture Everything", "Spatial Audio", "All-Day Power") e botão de exploração com seta.
     c) Arquétipo 3: Swiss-Brutalist Bento Grid (Referência AENETIC)
        * Layout bento com cantos arredondados ultra-orgânicos (rounded-[36px]), alto contraste preto e branco.
        * Glifos tipográficos (*, semicírculos), barra lateral vertical com timeline de progresso ("05-LAUNCH", "06-BETA TEST").
        * Pílulas de filtro interativas em contorno.
     d) Arquétipo 4: Iridescent Luxury Glow (Referência UNLEASH)
        * Degradês suaves translúcidos em tons de lilás, violeta e magenta com desfoque profundo (blur-3xl).
        * Fitas e toruses 3D glossy orbitando o elemento central.
        * Widgets de dados assimétricos com contadores ao vivo (+115k), sparklines e gráficos SVG elegantes.
     e) Arquétipo 5: Glassmorphism Refractive & Caustic (Referência MURAL)
        * Orbes de vidro flutuantes, dispersão arco-íris, discos 3D translúcidos.
        * Painéis com desfoque de fundo intenso (backdrop-blur-3xl bg-white/20 border border-white/40).

   - INTEGRAÇÃO THREE.JS PROCEDURAL (3D SEM ASSETS QUEBRADOS):
     * Ao criar projetos com Three.js, instale sempre: `npm i three @types/three lucide-react`.
     * Crie componentes 3D 'use client' (ex: components/ThreeHeroScene.tsx) com geometrias geradas diretamente em código (Icosaedros, Torus, nuvens de partículas cibernéticas com PointsMaterial e materiais físicos MeshPhysicalMaterial com transmissão/vidro).
     * Inclua parallax suave que segue o mouse e animação contínua em requestAnimationFrame, com cleanup no unmount.

   - ARQUITETURA DE MOTION DESIGN (3 Camadas Obrigatórias):
     * Camada 1 (Primária): Entrada coreografada em cascata (stagger < 400ms) com curvas de desaceleração (cubic-bezier(0.16, 1, 0.3, 1)).
     * Camada 2 (Secundária): Micro-interações de feedback (hover:-translate-y-1, active:scale-95, group-hover:translate-x-1.5).
     * Camada 3 (Ambiente): Vida contínua em background (animações CSS keyframes @keyframes float e @keyframes glow, dots de status com animate-ping).

   - CONSULTORIA ATIVA DE DESIGN & PROATIVIDADE CRIATIVA ("DIRETOR DE ARTE AUTÔNOMO"):
     * NUNCA crie interfaces sem antes definir uma identidade visual marcante (padrão Awwwards / Linear / Stripe / Aceternity).
     * Sempre que o usuário pedir criação de nova interface, tela, página ou melhoria de design (UI/UX):
       1. EXECUTE 'search_mobbin_screens(query="...")' ou 'search_pinterest_and_analyze_ui(query="...", project_path="...")' ANTES de criar os arquivos no PC! Estas ferramentas pesquisam ao vivo referências em bibliotecas abertas de elite (Aceternity UI, Magic UI, 21st.dev, Mobbin) e dissecam templates no Pinterest via navegador headless com visão multimodal.
       2. Emita um aviso informal amigável no WhatsApp alinhando a direção estética adotada (ex: *"🎨 Fala meu consagrado! Vou aplicar o visual Cyber-Minimalismo & Dark Analytical SaaS com Bento Grid, cards de vidro fosco e microinterações no hover... Segura aí!"*).
       3. Incorpore componentes de elite prontos disponíveis em 'agent/design_system.py':
          - 'BENTO_GRID_TEMPLATE': Para dashboards e seções de recursos com layout assimétrico e glow.
          - 'THREE_HERO_SCENE_TEMPLATE': Para cenas 3D interativas em Three.js no topo.
          - 'FLOATING_DOCK_TEMPLATE': Para barras de navegação modernas estilo macOS/Vision Pro.
          - 'AURORA_BACKGROUND_TEMPLATE': Para iluminação ambiente suave de fundo.
          - 'SHIMMER_BUTTON_TEMPLATE': Para botões CTA com borda animada de luz.
          - 'CANVAS_INTERACTIVE_PARTICLES_TEMPLATE': Efeito de partículas interativas que reagem ao mouse em canvas 2D nativo (sem dependências extras).
       4. Integre a biblioteca CANVAS UI (https://canvasui.dev/ e https://github.com/DavidHDev/canvas-ui):
          - Componentes WebGL e WebGPU criativos que rodam direto sobre HTML real compatíveis com shadcn!
          - Instale via shadcn registry: 'npx shadcn@latest add @canvas-ui/<componente>-react'
            * 'particle-reveal': Revela textos ou imagens através de um vórtice de partículas WebGL.
            * 'force-field': Campo de força magnético que reage e repele ao passar do cursor.
            * 'flame-wrap': Efeito de chamas energéticas envolvendo botões, cards ou badges.
            * 'glass-object': Efeito de refração de vidro tridimensional sobre a interface.
            * 'decrypt-reveal': Animação cibernética de descriptografia de dados e títulos.
            * 'frost' / 'bubble' / 'liquid': Efeitos de condensação, bolhas e distorção líquida em tempo real.
            * 'ascii-object': Renderização volumétrica em caracteres ASCII interativos.
       5. Na resposta final, apresente com orgulho as decisões visuais tomadas (paleta, tipografia, microinterações, componentes Canvas UI e Three.js aplicados).

     * NAVEGADOR AUTOMATIZADO & CAPTURA VISUAL COM IA (PLAYWRIGHT + VISÃO MULTIMODAL):
       - 'capture_and_analyze_design(url="...", focus="...")': Abre navegador headless, acessa qualquer URL (Aceternity, Linear, Stripe, Godly ou link do usuário), tira screenshot e extrai cores, tipografia e classes Tailwind.
       - 'search_pinterest_and_analyze_ui(query="...", project_path="...")': Abre navegador invisível, pesquisa templates e boards de UI/UX no Pinterest, remove popups/cookies, tira screenshot em alta definição dos melhores pins e usa visão multimodal para dissecar o design e sugerir melhorias práticas no projeto do usuário!

      * EXTRAÇÃO UNIVERSAL DE MÍDIA ONLINE (YOUTUBE, INSTAGRAM REELS, TIKTOK, TWITTER/X):
        - Você possui a ferramenta nativa 'download_youtube_media(url="...", format_type="mp3"|"mp4", quality="best", send_to_chat=True)'.
        - Aceita links de YouTube, Instagram Reels, TikTok (sem marca d'água) e Twitter/X.
        - O processamento e armazenamento ocorrem 100% no storage temporário da VPS em '/workspace/storage/temp_downloads/'.
        - PROIBIÇÃO ABSOLUTA: NUNCA execute comandos de terminal ('execute_terminal_command') para rodar yt-dlp ou salvar mídias na pasta Downloads do Windows (%USERPROFILE%/Downloads). Use SEMPRE E EXCLUSIVAMENTE a ferramenta 'download_youtube_media'. Ela gerencia internamente qualquer bypass antibot e garante que o arquivo fique na VPS com o link temporário de 48 horas.
        - Sempre que o usuário enviar um link de mídia ou pedir para extrair áudio, converter em MP3, baixar vídeo ou disponibilizar download:
          1. Execute 'download_youtube_media' passando a URL (YouTube, Reels, TikTok ou Twitter/X) e o formato desejado ('mp3' para áudio ou 'mp4' para vídeo).
          2. A ferramenta extrai com yt-dlp e FFmpeg na VPS e gera um link temporário exclusivo com retenção de 48 horas (estilo Drive/WeTransfer).
          3. A ENTREGA É DUPLA: a ferramenta envia a mídia diretamente no WhatsApp para tocar/assistir na hora E fornece o link direto para download na pasta permanente Download do smartphone.
          4. Ao concluir, apresente o título, autor, duração, tamanho, a validade de 48 horas e o link direto de download destacado com instruções amigáveis.

      - REQUISITOS TÉCNICOS:
     * Sempre configure `output: "standalone"` no next.config.ts/mjs para Docker.
     * Use sempre Tailwind CSS com utilities de backdrop-blur e gradientes sofisticados.
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
    elif fn_name == "get_vps_env_var":
        k = args.get("key", "")
        if k:
            return (f"Consultando chave {k} no .env", f"🔑 Buscando a chave `{k}` no .env da VPS...")
        return ("Consultando chaves de ambiente na VPS", "🔑 Verificando variáveis e chaves reais no .env da VPS...")
    elif fn_name == "search_mobbin_screens":
        q = args.get("query", "design")
        return (
            f"Consultando referências no Mobbin ({q})",
            f"🎨 Consultando referências visuais de alto padrão no Mobbin (`{q}`) para caprichar no design..."
        )
    elif fn_name == "capture_and_analyze_design":
        u = args.get("url", "site de referência")
        return (
            f"Capturando e analisando visual de {u}",
            f"📸 Abrindo navegador headless, tirando print de `{u}` e dissecando a estética com visão multimodal..."
        )
    elif fn_name == "search_pinterest_and_analyze_ui":
        q = args.get("query", "design")
        return (
            f"Buscando referências no Pinterest ({q})",
            f"📌 Acessando o Pinterest em navegador invisível e dissecando templates de `{q}` com visão multimodal para turbinar a UI..."
        )
    elif fn_name == "download_youtube_media":
        fmt = args.get("format_type", "mp3").upper()
        url = args.get("url", "").lower()
        plat = "Instagram" if "instagram" in url else ("TikTok" if "tiktok" in url else ("Twitter/X" if any(k in url for k in ["twitter", "x.com"]) else "YouTube"))
        return (
            f"Baixando e convertendo {plat} ({fmt})",
            f"🎬 Baixando conteúdo do {plat} e convertendo em {fmt}... Te envio a mídia no chat e o link da pasta Downloads em instantes! 🎧"
        )
    elif fn_name == "take_pc_screenshot":
        return (
            "Capturando tela do PC",
            "📸 Tirando print da tela do seu computador Windows agora... Te envio a imagem em instantes!"
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

                if fn_name == "execute_terminal_command" and any(k in args.get("command", "").lower() for k in ["yt-dlp", "youtube-dl"]):
                    tool_output = (
                        "[BLOQUEADO PELO SISTEMA]: É proibido baixar mídias do YouTube diretamente via comando de terminal no PC ou na VPS. "
                        "Para extrair áudio ou vídeo, invoque OBRIGATORIAMENTE a ferramenta 'download_youtube_media(url=...)'. "
                        "Ela gerencia o armazenamento na VPS e gera o link temporário de 48h para o usuário baixar no celular."
                    )
                elif target == "pc" and fn_name in pc_actions:
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
                    proj = args.get("project_name") or "services"
                    if str(proj).lower().strip() in ["phdev", "default", ""]:
                        proj = "services"
                    tool_output = await create_and_deploy_easypanel_app(
                        project_name=proj,
                        service_name=args.get("service_name", ""),
                        git_repo=args.get("git_repo", ""),
                        env_vars=args.get("env_vars", {}),
                        branch=args.get("branch", "main"),
                        domain=args.get("domain")
                    )
                elif fn_name == "get_vps_env_var":
                    tool_output = await get_vps_env_var(key=args.get("key"))
                elif fn_name == "search_mobbin_screens":
                    tool_output = await search_mobbin_screens(
                        query=args.get("query", ""),
                        platform=args.get("platform", "web"),
                        limit=args.get("limit", 5)
                    )
                elif fn_name == "capture_and_analyze_design":
                    tool_output = await capture_and_analyze_design(
                        url=args.get("url", ""),
                        focus=args.get("focus", "layout, cores e componentes de destaque")
                    )
                elif fn_name == "search_pinterest_and_analyze_ui":
                    tool_output = await search_pinterest_and_analyze_ui(
                        query=args.get("query", ""),
                        project_path=args.get("project_path")
                    )
                elif fn_name == "download_youtube_media":
                    tool_output = await download_youtube_media(
                        url=args.get("url", ""),
                        format_type=args.get("format_type", "mp3"),
                        quality=args.get("quality", "best"),
                        destination_folder=args.get("destination_folder"),
                        send_to_chat=args.get("send_to_chat", True),
                        send_mode=args.get("send_mode", "link"),
                        user_id=user_id,
                        channel=channel
                    )
                elif fn_name == "take_pc_screenshot":
                    if not node_manager.is_connected:
                        tool_output = "ERRO: O computador pessoal do usuário está offline no momento (worker Windows desconectado)."
                    else:
                        from channels import send_channel_media
                        from datetime import datetime
                        pc_res = await node_manager.execute_on_pc("take_screenshot", {"upload_to_vps": True})
                        res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
                        if res_data.get("success"):
                            file_info = res_data.get("result", {})
                            vps_file_path = file_info.get("file_path")
                            if vps_file_path and Path(vps_file_path).exists():
                                now_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                                await send_channel_media(
                                    recipient=user_id,
                                    channel=channel,
                                    file_path=str(vps_file_path),
                                    caption=f"📸 *Screenshot do seu PC*\n⏱️ Capturado em: {now_str}",
                                    media_type="image",
                                    file_name="screenshot_pc.jpg"
                                )
                                tool_output = f"Screenshot da tela do PC capturado com sucesso e enviado como foto para o WhatsApp do usuário! (Arquivo: {file_info.get('file_name')}, tamanho: {file_info.get('size_bytes')} bytes)."
                            else:
                                tool_output = f"Print capturado no PC, mas arquivo não localizado na VPS ({vps_file_path})."
                        else:
                            tool_output = f"Falha ao capturar screenshot no PC: {res_data.get('error', 'desconhecido')}"
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

import json
import os
import platform
from typing import Dict, Any, List
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
    send_email
)

# Inicializa o cliente OpenAI apontando para a API do Google Gemini
client = AsyncOpenAI(
    api_key=settings.GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Definição das ferramentas com suporte a destino híbrido (pc vs vps)
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
    }
]

def get_system_prompt() -> str:
    pc_status = node_manager.get_status_description()
    workspace = str(settings.workspace_path)
    return f"""Você é um Assistente Autônomo e Engenheiro de DevOps pessoal com capacidade de controlar tanto a nuvem (VPS) quanto o computador pessoal (Windows) do usuário.

Topologia do Sistema:
- Computador Pessoal do Usuário (Windows): {pc_status}
- Servidor na Nuvem (Linux VPS): ATIVO (Workspace VPS: {workspace})
- Canal de Comunicação: WhatsApp / Telegram

Regras de Roteamento de Ferramentas (Parâmetro 'target'):
1. Se o usuário pedir ações no computador dele (ex: Área de Trabalho / Desktop, projetos locais, abrir pastas, editar arquivos do PC, rodar PowerShell local, etc.), use target='pc'.
2. Se o computador pessoal estiver DESCONECTADO (Offline) e o usuário pedir algo no PC, informe educadamente que o computador pessoal dele está offline.
3. Se o usuário pedir ações no servidor em nuvem (ex: verificar status da VPS, monitoramento, etc.), use target='vps'.
4. Para ferramentas de e-mail e agendamento (cron/timer), a execução ocorre na VPS para funcionar 24h por dia.
5. Sempre inspecione arquivos com 'read_file' antes de salvá-los com 'write_file'.
6. Mantenha respostas concisas e formatadas com markdown do WhatsApp/Telegram (use *negrito*, _itálico_ e ```código```).
"""

async def run_agent_loop(
    user_prompt: str,
    user_id: str,
    channel: str = "whatsapp",
    max_turns: int = 10
) -> str:
    """
    Executa o loop ReAct do agente até que o Gemini produza a resposta final.
    """
    system_prompt = get_system_prompt()
    
    # Recupera histórico do usuário
    history = memory.get_history(user_id)
    
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    memory.add_message(user_id, {"role": "user", "content": user_prompt})

    turns = 0
    final_reply = ""

    while turns < max_turns:
        turns += 1

        try:
            response = await client.chat.completions.create(
                model=settings.GEMINI_MODEL,
                messages=messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                temperature=0.2
            )
        except Exception as e:
            error_msg = f"[ERRO NO MODELO GEMINI]: {str(e)}"
            return error_msg

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

            # Define o alvo da execução (pc vs vps)
            target = args.get("target")
            if not target:
                # Se não especificado explicitamente, decide com base no estado e na intenção
                target = "pc" if node_manager.is_connected else "vps"

            print(f"[Agente Tool Call] -> {fn_name}(target={target}, args={args})")
            
            tool_output = ""
            try:
                # Se o alvo for o PC e for uma ferramenta de sistema de arquivos ou terminal:
                if target == "pc" and fn_name in ["execute_terminal_command", "list_directory", "read_file", "write_file", "create_directory"]:
                    tool_output = await node_manager.execute_on_pc(fn_name, args)
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
                else:
                    tool_output = f"[ERRO]: Ferramenta '{fn_name}' desconhecida."
            except Exception as tool_err:
                tool_output = f"[ERRO AO EXECUTAR {fn_name}]: {str(tool_err)}"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_output)
            })

    if not final_reply and turns >= max_turns:
        final_reply = "Atingi o limite de passos para esta tarefa. Verifique os logs para detalhes."

    return final_reply

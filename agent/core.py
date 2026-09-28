import json
import os
import platform
from typing import Dict, Any, List
from openai import AsyncOpenAI
from config import settings
from .memory import memory
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

# Definição das ferramentas no padrão OpenAI / Gemini Function Calling
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_terminal_command",
            "description": "Executa comandos no shell do sistema operacional (Bash no Linux ou PowerShell no Windows). Use para instalar pacotes, rodar scripts, verificar status, containers docker, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "O comando completo a ser executado."
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Opcional. Caminho da pasta onde executar o comando."
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
                        "description": "Caminho do diretório (padrão é '.' para a raiz do workspace)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um arquivo de texto com número de linhas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo a ser lido."
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
            "description": "Cria ou substitui completamente o conteúdo de um arquivo. Use para criar novos scripts ou salvar código corrigido.",
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
            "description": "Programa uma tarefa para rodar daqui a N minutos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_minutes": {
                        "type": "integer",
                        "description": "Minutos de espera até executar a tarefa."
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Instrução exata do que o agente deve fazer ao despertar."
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
            "description": "Programa uma tarefa recorrente usando expressão cron (ex: '0 9 * * *' para todo dia às 09:00).",
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
            "description": "Dispara um e-mail através das configurações SMTP.",
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
    os_name = platform.system()
    workspace = str(settings.workspace_path)
    return f"""Você é um Assistente Autônomo e Engenheiro de DevOps pessoal com acesso direto ao terminal da máquina e ao sistema de arquivos.

Contexto do Ambiente:
- Sistema Operacional: {os_name}
- Diretório de Trabalho Padrão: {workspace}
- Canal de Comunicação: WhatsApp / Telegram

Regras de Operação:
1. Você tem ferramentas para rodar comandos de terminal, ler/escrever arquivos, criar pastas, agendar tarefas e enviar e-mails.
2. Quando o usuário pedir para consertar código ou inspecionar um arquivo, SEMPRE use 'read_file' primeiro para entender o código existente antes de reescrevê-lo com 'write_file'.
3. Sempre que criar ou editar um script ou código, execute-o ou teste-o usando 'execute_terminal_command' para garantir que não há erros de sintaxe ou execução.
4. Mantenha suas mensagens finais formatadas para mensageiros como WhatsApp/Telegram (use *negrito*, _itálico_ e blocos de código com ```). Seja conciso e direto no resultado.
5. Se o usuário pedir para agendar uma tarefa, use 'schedule_timer' ou 'schedule_cron'.
6. Nunca exponha senhas ou dados confidenciais do arquivo .env.
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
    
    # Monta lista de mensagens com system prompt no início
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    # Adiciona ao histórico a pergunta do usuário
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

        # Se não há chamadas de ferramenta, temos a resposta final
        if not msg.tool_calls:
            final_reply = msg.content or "Tarefa concluída."
            memory.add_message(user_id, {"role": "assistant", "content": final_reply})
            break

        # Processa cada chamada de ferramenta
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            raw_args = tool_call.function.arguments
            
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}

            print(f"[Agente Tool Call] -> {fn_name}({args})")
            
            # Despacho da ferramenta
            tool_output = ""
            try:
                if fn_name == "execute_terminal_command":
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

            # Devolve a resposta da ferramenta para a conversa
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_output)
            })

    if not final_reply and turns >= max_turns:
        final_reply = "Atingi o limite de passos para esta tarefa. Verifique os logs para detalhes."

    return final_reply

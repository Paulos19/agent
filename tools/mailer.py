import aiosmtplib
from email.message import EmailMessage
from typing import Optional
from config import settings

async def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False
) -> str:
    """
    Envia um e-mail através das configurações SMTP.
    
    Args:
        to_email: Endereço de destino.
        subject: Assunto do e-mail.
        body: Mensagem do e-mail (texto ou HTML).
        is_html: Se True, renderiza o corpo como HTML.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASS or not settings.SMTP_HOST:
        return "[ERRO]: Configurações SMTP incompletas no arquivo .env (SMTP_HOST, SMTP_USER, SMTP_PASS)."

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    if is_html:
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    try:
        use_tls = settings.SMTP_PORT == 465 or bool(settings.EMAIL_SERVER_SECURE)
        start_tls = settings.SMTP_PORT == 587 and not use_tls

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=30.0
        )
        return f"[SUCESSO]: E-mail enviado com sucesso para '{to_email}'."
    except Exception as e:
        return f"[ERRO AO ENVIAR E-MAIL]: {str(e)}"

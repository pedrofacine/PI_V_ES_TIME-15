import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_reset_email(to_email: str, token: str) -> None:
    reset_link = f"{FRONTEND_URL}/new-password?token={token}"

    resend.Emails.send({
        "from": FROM_EMAIL,
        "to": to_email,
        "subject": "Redefinição de senha — SmartScout",
        "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: auto;">
                <h2>Redefinir sua senha</h2>
                <p>Clique no botão abaixo para criar uma nova senha. O link expira em 1 hora.</p>
                <a href="{reset_link}"
                   style="display:inline-block; padding: 12px 24px; background:#2872A1;
                          color:white; border-radius:8px; text-decoration:none; font-weight:600;">
                    Redefinir senha
                </a>
                <p style="margin-top:24px; color:#999; font-size:12px;">
                    Se você não solicitou isso, ignore este e-mail.
                </p>
            </div>
        """,
    })
import subprocess
import sys
import os
import smtplib
from email.message import EmailMessage

def run_mypy():
    # lance mypy sur tout le dépôt
    proc = subprocess.run(["mypy", "."], capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr

def send_email(subject, body, to_addr):
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    if not user or not pwd:
        print("SMTP_USER ou SMTP_PASS manquant dans les secrets. Email non envoyé.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(user, pwd)
            smtp.send_message(msg)
        print("Email envoyé à", to_addr)
    except Exception as e:
        print("Erreur envoi email:", e)

def main():
    code, output = run_mypy()
    if code == 0:
        print("✅ mypy: pas d'erreurs de typage.")
        sys.exit(0)

    # mypy a détecté des erreurs -> envoyer mail
    subject = "❌ Échec du typage Python - Pull Request bloquée"
    body = (
        "Bonjour,\n\n"
        "Le contrôle automatique de typage a détecté des problèmes dans votre Pull Request.\n\n"
        "=== Rapport mypy ===\n\n"
        f"{output}\n\n"
        "Conseils :\n"
        "- Ajoutez des annotations de type (ex: def f(x: int) -> str: ...)\n"
        "- Exécutez `mypy .` en local pour voir les erreurs exactes.\n\n"
        "Le merge a été bloqué jusqu'à correction.\n"
        "\nCordialement,\nLe CI"
    )

    to_addr = os.getenv("SMTP_USER")
    send_email(subject, body, to_addr)

    print("mypy a échoué. Détails ci-dessous:\n", output)
    sys.exit(1)

if __name__ == "__main__":
    main()

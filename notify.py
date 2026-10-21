"""E-posta (Gmail SMTP) ve WhatsApp (CallMeBot) bildirimleri — ikisi de ücretsiz."""
import os
import smtplib
import time
from email.message import EmailMessage

import requests


def send_email(subject: str, body: str) -> bool:
    user = os.environ.get("MAIL_USER")
    pwd = os.environ.get("MAIL_APP_PASSWORD")
    to = os.environ.get("MAIL_TO")
    if not (user and pwd and to):
        print("E-posta ayarlı değil, atlandı.")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, user, to
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:
        print("E-posta hatası:", e)
        return False


def _chunks(header, lines, limit=1200):
    cur = header
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            yield cur
            cur = header + " (devam)"
        cur += "\n" + ln
    yield cur


def send_whatsapp(header: str, lines) -> bool:
    phone = os.environ.get("WA_PHONE")
    key = os.environ.get("WA_APIKEY")
    if not (phone and key):
        print("WhatsApp ayarlı değil, atlandı.")
        return False
    ok = True
    for part in _chunks(header, lines):
        try:
            r = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": phone, "text": part, "apikey": key},
                timeout=30,
            )
            ok &= r.status_code == 200
        except Exception as e:
            print("WhatsApp hatası:", e)
            ok = False
        time.sleep(3)
    return ok


def send_all(subject: str, lines) -> bool:
    """En az bir kanal başarılıysa True."""
    mail_ok = send_email(subject, subject + "\n\n" + "\n".join(lines))
    wa_ok = send_whatsapp(subject, lines)
    return mail_ok or wa_ok

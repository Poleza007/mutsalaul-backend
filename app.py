"""
Email-оповещение — бэкенд для сайта АМО «Село Муцалаул»
Запуск: python app.py
API работает на http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, re, datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

BASE       = os.path.dirname(__file__)
EMAILS_FILE = os.path.join(BASE, "email_subscribers.json")
LOG_FILE    = os.path.join(BASE, "email_log.json")

ADMIN_PASS = "admin2025"
GMAIL_USER = "kamiltapaev@gmail.com"
GMAIL_PASS = "yjjfgcqwptbxujiw"


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/subscribe-email", methods=["POST"])
def subscribe_email():
    data  = request.get_json(force=True)
    email = data.get("email", "").strip().lower()

    if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"status": "error", "message": "Неверный формат email"})

    subs = load_json(EMAILS_FILE)
    if email in subs:
        return jsonify({"status": "already", "message": "Этот email уже подписан"})

    subs.append(email)
    save_json(EMAILS_FILE, subs)
    return jsonify({"status": "ok", "message": "Вы подписаны на Email-оповещения!"})


@app.route("/unsubscribe-email", methods=["POST"])
def unsubscribe_email():
    data  = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    subs  = load_json(EMAILS_FILE)
    if email in subs:
        subs.remove(email)
        save_json(EMAILS_FILE, subs)
        return jsonify({"status": "ok", "message": "Email отписан"})
    return jsonify({"status": "not_found", "message": "Email не найден"})


@app.route("/count", methods=["GET"])
def count():
    return jsonify({"email": len(load_json(EMAILS_FILE))})


@app.route("/send", methods=["POST"])
def send_all():
    data     = request.get_json(force=True)
    password = data.get("password", "")
    message  = data.get("message", "").strip()

    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"})
    if not message:
        return jsonify({"status": "error", "message": "Сообщение пустое"})

    emails    = load_json(EMAILS_FILE)
    if not emails:
        return jsonify({"status": "error", "message": "Нет подписчиков"})

    timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    log       = load_json(LOG_FILE)
    ok        = 0
    fail      = 0

    server = None
    for attempt in range(3):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            break
        except Exception:
            server = None
            import time; time.sleep(2)

    if server is None:
        fail += len(emails)
        log.append({"time": timestamp, "to": "все",
                    "message": message, "status": "ошибка: нет подключения к почтовому серверу"})
    else:
        for email in emails:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = "Оповещение — АМО «Село Муцалаул»"
                msg["From"]    = f"АМО «Село Муцалаул» <{GMAIL_USER}>"
                msg["To"]      = email
                html = f"""
                <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
                  <div style="background:#1a3a6b;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
                    <b style="font-size:1.1rem;">АМО «Село Муцалаул»</b><br>
                    <span style="opacity:.8;font-size:.85rem;">Официальное оповещение</span>
                  </div>
                  <div style="background:#f9fafb;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
                    <p style="font-size:1rem;color:#111;">{message}</p>
                    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
                    <p style="font-size:.8rem;color:#6b7280;">
                      Хасавюртовский район, с. Муцалаул<br>
                      Пн–Пт: 9:00–18:00 · momutsalaul@mail.ru
                    </p>
                  </div>
                </div>"""
                msg.attach(MIMEText(message, "plain", "utf-8"))
                msg.attach(MIMEText(html, "html", "utf-8"))
                server.sendmail(GMAIL_USER, email, msg.as_string())
                ok += 1
                log.append({"time": timestamp, "to": email,
                            "message": message, "status": "отправлено"})
            except Exception as e:
                fail += 1
                log.append({"time": timestamp, "to": email,
                            "message": message, "status": f"ошибка: {e}"})
        server.quit()

    save_json(LOG_FILE, log)
    return jsonify({"status": "ok", "email_sent": ok, "email_fail": fail})


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify(load_json(LOG_FILE))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Сервер запущен: http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)

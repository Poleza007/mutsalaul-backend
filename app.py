"""
Email-оповещение — бэкенд для сайта АМО «Село Муцалаул»
Запуск: python app.py
API работает на http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, re, datetime, uuid
import resend

app = Flask(__name__)
CORS(app)

BASE         = os.path.dirname(__file__)
EMAILS_FILE  = os.path.join(BASE, "email_subscribers.json")
PENDING_FILE = os.path.join(BASE, "pending_subscribers.json")
LOG_FILE     = os.path.join(BASE, "email_log.json")
NEWS_FILE    = os.path.join(BASE, "..", "site", "data", "news.json")
STAFF_FILE   = os.path.join(BASE, "..", "site", "data", "staff.json")

BACKEND_URL  = "https://mutsalaul-backend.onrender.com"
SITE_URL     = "https://mutsalaul.netlify.app"

ADMIN_PASS  = "admin2025"
RESEND_KEY  = "re_Lr5atSdK_3RxJaUxtndpNPfyrbeJh3dmi"
resend.api_key = RESEND_KEY


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _html_page(title, body):
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — АМО «Село Муцалаул»</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:520px;margin:80px auto;text-align:center;padding:0 20px;}}
  h2{{color:#1a3a6b;margin-bottom:12px;}}
  p{{color:#444;line-height:1.6;}}
  .btn{{display:inline-block;margin-top:24px;padding:12px 28px;background:#1a3a6b;color:#fff;
        border-radius:8px;text-decoration:none;font-size:1rem;}}
</style>
</head>
<body>
  <h2>{title}</h2>
  <p>{body}</p>
  <a class="btn" href="{SITE_URL}">← Вернуться на сайт</a>
</body>
</html>"""


@app.route("/subscribe-email", methods=["POST"])
def subscribe_email():
    data  = request.get_json(force=True)
    email = data.get("email", "").strip().lower()

    if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"status": "error", "message": "Неверный формат email"})

    # Уже подтверждён
    subs = load_json(EMAILS_FILE)
    if email in subs:
        return jsonify({"status": "already", "message": "Этот email уже подписан"})

    # Уже ожидает подтверждения
    pending = load_json(PENDING_FILE)
    if any(p["email"] == email for p in pending):
        return jsonify({"status": "check_email",
                        "message": "Письмо уже отправлено. Проверьте почту и нажмите «Подтвердить»."})

    # Создаём токен и сохраняем
    token   = str(uuid.uuid4())
    expires = (datetime.datetime.now() + datetime.timedelta(hours=24)).isoformat()
    pending.append({"email": email, "token": token, "expires": expires})
    save_json(PENDING_FILE, pending)

    # Отправляем письмо с подтверждением
    confirm_url = f"{BACKEND_URL}/confirm?token={token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:#1a3a6b;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
        <b style="font-size:1.1rem;">АМО «Село Муцалаул»</b><br>
        <span style="opacity:.8;font-size:.85rem;">Подтверждение подписки</span>
      </div>
      <div style="background:#f9fafb;padding:28px 24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
        <p style="font-size:1rem;color:#111;margin-top:0;">
          Вы оставили заявку на подписку по адресу <b>{email}</b>.<br>
          Нажмите кнопку ниже, чтобы подтвердить подписку на Email-оповещения АМО «Село Муцалаул».
        </p>
        <div style="text-align:center;margin:28px 0;">
          <a href="{confirm_url}"
             style="background:#1a3a6b;color:#fff;padding:14px 32px;border-radius:8px;
                    text-decoration:none;font-size:1rem;display:inline-block;">
            ✓ Подтвердить подписку
          </a>
        </div>
        <p style="font-size:.8rem;color:#6b7280;margin-bottom:0;">
          Ссылка действительна 24 часа. Если вы не оставляли заявку — просто проигнорируйте письмо.<br>
          Хасавюртовский район, с. Муцалаул · Пн–Пт 9:00–18:00
        </p>
      </div>
    </div>"""

    try:
        resend.Emails.send({
            "from":    "АМО Муцалаул <onboarding@resend.dev>",
            "to":      [email],
            "subject": "Подтвердите подписку — АМО «Село Муцалаул»",
            "html":    html,
            "text":    f"Подтвердите подписку, перейдя по ссылке: {confirm_url}"
        })
    except Exception as e:
        pending = [p for p in load_json(PENDING_FILE) if p["email"] != email]
        save_json(PENDING_FILE, pending)
        return jsonify({"status": "error", "message": "Не удалось отправить письмо"})

    return jsonify({"status": "check_email",
                    "message": "Письмо отправлено! Проверьте почту и нажмите «Подтвердить подписку»."})


@app.route("/confirm", methods=["GET"])
def confirm_email():
    token   = request.args.get("token", "").strip()
    pending = load_json(PENDING_FILE)
    item    = next((p for p in pending if p["token"] == token), None)

    if not item:
        return _html_page("Ссылка недействительна",
                          "Эта ссылка уже использована или не существует."), 400

    if datetime.datetime.fromisoformat(item["expires"]) < datetime.datetime.now():
        save_json(PENDING_FILE, [p for p in pending if p["token"] != token])
        return _html_page("Ссылка устарела",
                          "Срок действия ссылки (24 ч) истёк. Подпишитесь заново на сайте."), 400

    email = item["email"]
    subs  = load_json(EMAILS_FILE)
    if email not in subs:
        subs.append(email)
        save_json(EMAILS_FILE, subs)
    save_json(PENDING_FILE, [p for p in pending if p["token"] != token])

    return _html_page("Подписка подтверждена!",
                      f"Адрес <b>{email}</b> добавлен в список оповещений.<br>"
                      "Теперь вы будете получать важные новости и объявления администрации.")


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


@app.route("/check-email", methods=["GET"])
def check_email():
    email = request.args.get("email", "").strip().lower()
    if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"subscribed": False})
    subs = load_json(EMAILS_FILE)
    return jsonify({"subscribed": email in subs})


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

    for email in emails:
        try:
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
            resend.Emails.send({
                "from":    "АМО Муцалаул <onboarding@resend.dev>",
                "to":      [email],
                "subject": "Оповещение — АМО «Село Муцалаул»",
                "html":    html,
                "text":    message
            })
            ok += 1
            log.append({"time": timestamp, "to": email,
                        "message": message, "status": "отправлено"})
        except Exception as e:
            fail += 1
            log.append({"time": timestamp, "to": email,
                        "message": message, "status": f"ошибка: {e}"})

    save_json(LOG_FILE, log)
    return jsonify({"status": "ok", "email_sent": ok, "email_fail": fail})


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify(load_json(LOG_FILE))


# ── Управление новостями ──────────────────────────────────────────

@app.route("/api/news", methods=["GET"])
def news_list():
    news = load_json(NEWS_FILE)
    return jsonify(sorted(news, key=lambda x: x.get("id", 0), reverse=True))


@app.route("/api/news", methods=["POST"])
def news_add():
    password = request.form.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    title    = request.form.get("title", "").strip()
    preview  = request.form.get("preview", "").strip()
    text     = request.form.get("text", "").strip()
    date     = request.form.get("date", "").strip()
    category = request.form.get("category", "Новости").strip()

    if not title or not preview or not text or not date:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    news   = load_json(NEWS_FILE)
    new_id = max((n.get("id", 0) for n in news), default=0) + 1

    image_path = ""
    file = request.files.get("image")
    if file and file.filename:
        ext      = os.path.splitext(file.filename)[1].lower() or ".jpg"
        filename = f"news_{new_id}{ext}"
        img_dir  = os.path.join(BASE, "..", "site", "images", "news")
        os.makedirs(img_dir, exist_ok=True)
        file.save(os.path.join(img_dir, filename))
        image_path = f"images/news/{filename}"

    item = {"id": new_id, "date": date, "title": title,
            "preview": preview, "text": text, "category": category}
    if image_path:
        item["image"] = image_path

    news.append(item)
    save_json(NEWS_FILE, news)
    return jsonify({"status": "ok", "id": new_id})


@app.route("/api/news/<int:news_id>", methods=["PUT"])
def news_update(news_id):
    password = request.form.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    title    = request.form.get("title", "").strip()
    preview  = request.form.get("preview", "").strip()
    text     = request.form.get("text", "").strip()
    date     = request.form.get("date", "").strip()
    category = request.form.get("category", "Новости").strip()

    if not title or not preview or not text or not date:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    news = load_json(NEWS_FILE)
    item = next((n for n in news if n.get("id") == news_id), None)
    if not item:
        return jsonify({"status": "error", "message": "Новость не найдена"}), 404

    item["title"]    = title
    item["preview"]  = preview
    item["text"]     = text
    item["date"]     = date
    item["category"] = category

    file = request.files.get("image")
    if file and file.filename:
        ext      = os.path.splitext(file.filename)[1].lower() or ".jpg"
        filename = f"news_{news_id}{ext}"
        img_dir  = os.path.join(BASE, "..", "site", "images", "news")
        os.makedirs(img_dir, exist_ok=True)
        file.save(os.path.join(img_dir, filename))
        item["image"] = f"images/news/{filename}"

    save_json(NEWS_FILE, news)
    return jsonify({"status": "ok"})


@app.route("/api/news/<int:news_id>", methods=["DELETE"])
def news_delete(news_id):
    data     = request.get_json(force=True)
    password = data.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    news    = load_json(NEWS_FILE)
    updated = [n for n in news if n.get("id") != news_id]
    if len(updated) == len(news):
        return jsonify({"status": "error", "message": "Новость не найдена"}), 404

    save_json(NEWS_FILE, updated)
    return jsonify({"status": "ok"})


# ── Управление сотрудниками ───────────────────────────────────────

@app.route("/api/staff", methods=["GET"])
def staff_list():
    return jsonify(load_json(STAFF_FILE))


@app.route("/api/staff", methods=["POST"])
def staff_add():
    password = request.form.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    name     = request.form.get("name", "").strip()
    position = request.form.get("position", "").strip()
    phone    = request.form.get("phone", "").strip()

    if not name or not position:
        return jsonify({"status": "error", "message": "Укажите имя и должность"}), 400

    staff  = load_json(STAFF_FILE)
    new_id = max((s.get("id", 0) for s in staff), default=0) + 1

    photo = ""
    file  = request.files.get("photo")
    if file and file.filename:
        ext     = os.path.splitext(file.filename)[1].lower() or ".jpg"
        fname   = f"staff_{new_id}{ext}"
        img_dir = os.path.join(BASE, "..", "site", "images", "staff")
        os.makedirs(img_dir, exist_ok=True)
        file.save(os.path.join(img_dir, fname))
        photo = f"images/staff/{fname}"

    staff.append({"id": new_id, "name": name, "position": position,
                  "phone": phone, "photo": photo})
    save_json(STAFF_FILE, staff)
    return jsonify({"status": "ok", "id": new_id})


@app.route("/api/staff/<int:staff_id>", methods=["PUT"])
def staff_update(staff_id):
    password = request.form.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    name     = request.form.get("name", "").strip()
    position = request.form.get("position", "").strip()
    phone    = request.form.get("phone", "").strip()

    if not name or not position:
        return jsonify({"status": "error", "message": "Укажите имя и должность"}), 400

    staff = load_json(STAFF_FILE)
    item  = next((s for s in staff if s.get("id") == staff_id), None)
    if not item:
        return jsonify({"status": "error", "message": "Сотрудник не найден"}), 404

    item["name"]     = name
    item["position"] = position
    item["phone"]    = phone

    file = request.files.get("photo")
    if file and file.filename:
        ext     = os.path.splitext(file.filename)[1].lower() or ".jpg"
        fname   = f"staff_{staff_id}{ext}"
        img_dir = os.path.join(BASE, "..", "site", "images", "staff")
        os.makedirs(img_dir, exist_ok=True)
        file.save(os.path.join(img_dir, fname))
        item["photo"] = f"images/staff/{fname}"

    save_json(STAFF_FILE, staff)
    return jsonify({"status": "ok"})


@app.route("/api/staff/<int:staff_id>", methods=["DELETE"])
def staff_delete(staff_id):
    data     = request.get_json(force=True)
    password = data.get("password", "")
    if password != ADMIN_PASS:
        return jsonify({"status": "error", "message": "Неверный пароль"}), 403

    staff   = load_json(STAFF_FILE)
    updated = [s for s in staff if s.get("id") != staff_id]
    if len(updated) == len(staff):
        return jsonify({"status": "error", "message": "Сотрудник не найден"}), 404

    save_json(STAFF_FILE, updated)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Сервер запущен: http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)

import os
import string
import random
from flask import Flask, request, render_template_string
import telebot
from telebot import types
from database import get_connection, init_db

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_STORAGE = int(os.getenv("CHANNEL_STORAGE"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")
BASE_URL = os.getenv("BASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

init_db()

# ========= UTIL =========
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def save_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Start", "Upload")
    markup.row("GetCode", "MyCode")
    markup.row("Notification")
    return markup

# ========= START =========
@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "Start")
def start(message):
    save_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "🔥 Welcome to FileBot Premium\nUpload file dan dapatkan link + code.",
        reply_markup=main_menu()
    )

# ========= UPLOAD =========
@bot.message_handler(func=lambda m: m.text == "Upload")
def upload_info(message):
    bot.send_message(message.chat.id, "📤 Kirim file/video sekarang.")

@bot.message_handler(content_types=['document', 'video'])
def handle_file(message):
    save_user(message.from_user.id)

    code = generate_code()

    forwarded = bot.forward_message(
        CHANNEL_STORAGE,
        message.chat.id,
        message.message_id
    )

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO files (code, message_id, user_id) VALUES (%s,%s,%s)",
        (code, forwarded.message_id, message.from_user.id)
    )
    conn.commit()
    cur.close()
    conn.close()

    link = f"{BASE_URL}/file/{code}?user_id={message.from_user.id}"

    bot.reply_to(
        message,
        f"✅ File berhasil disimpan permanen!\n\n🔗 {link}\n🔑 Code: {code}"
    )

# ========= GET CODE =========
@bot.message_handler(func=lambda m: m.text == "GetCode")
def ask_code(message):
    msg = bot.send_message(message.chat.id, "Masukkan kode:")
    bot.register_next_step_handler(msg, process_code)

def process_code(message):
    code = message.text.upper()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT code FROM files WHERE code=%s", (code,))
    data = cur.fetchone()
    cur.close()
    conn.close()

    if not data:
        bot.reply_to(message, "❌ Code tidak ditemukan")
        return

    link = f"{BASE_URL}/file/{code}?user_id={message.from_user.id}"
    bot.reply_to(message, f"🔗 {link}")

# ========= MY CODE =========
@bot.message_handler(func=lambda m: m.text == "MyCode")
def my_code(message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT code, views FROM files WHERE user_id=%s ORDER BY created_at DESC",
        (message.from_user.id,)
    )
    data = cur.fetchall()
    cur.close()
    conn.close()

    if not data:
        bot.reply_to(message, "Belum ada file.")
        return

    text = "📁 File kamu:\n\n"
    for d in data:
        text += f"{d[0]} | 👁 {d[1]} views\n"

    bot.reply_to(message, text)

# ========= NOTIFICATION =========
@bot.message_handler(func=lambda m: m.text == "Notification")
def notification(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Hanya admin.")
        return

    msg = bot.send_message(message.chat.id, "Kirim pesan broadcast:")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    count = 0
    for u in users:
        try:
            bot.send_message(u[0], message.text)
            count += 1
        except:
            pass

    bot.reply_to(message, f"✅ Broadcast terkirim ke {count} user.")

# ========= WEB FILE =========
HTML_FILE = """
<html>
<head>
<title>File Viewer</title>
<style>
body{background:#0f172a;color:white;font-family:Arial;text-align:center}
.card{background:#1e293b;margin:30px auto;padding:20px;width:350px;border-radius:15px}
button{padding:10px 20px;border:none;border-radius:8px;background:#3b82f6;color:white}
a{text-decoration:none;color:white}
</style>
</head>
<body>
<h2>🎬 File Viewer</h2>
{% if not joined %}
<div class="card">
<p>⚠️ Wajib join channel</p>
<a href="https://t.me/{{channel}}" target="_blank">
<button>Join Channel</button></a><br><br>
<a href="?user_id={{user_id}}">
<button>Verify Join</button></a>
</div>
{% else %}
<div class="card">
<p>🔑 Code: {{code}}</p>
<p>👁 {{views}} views</p>
<a href="{{file_url}}" target="_blank">
<button>Open File</button></a>
</div>
{% endif %}
</body>
</html>
"""

@app.route("/file/<code>")
def file_page(code):
    user_id = request.args.get("user_id")
    if not user_id:
        return "User ID required"

    user_id = int(user_id)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT message_id, views FROM files WHERE code=%s", (code,))
    data = cur.fetchone()

    if not data:
        return "File tidak ditemukan"

    message_id, views = data
    joined = is_user_joined(user_id)

    if joined:
        cur.execute("UPDATE files SET views=views+1 WHERE code=%s", (code,))
        conn.commit()

    cur.close()
    conn.close()

    file_url = f"https://t.me/c/{str(CHANNEL_STORAGE)[4:]}/{message_id}"

    return render_template_string(
        HTML_FILE,
        joined=joined,
        channel=FORCE_CHANNEL.replace("@",""),
        user_id=user_id,
        code=code,
        views=views,
        file_url=file_url
    )

if __name__ == "__main__":
    bot.infinity_polling()

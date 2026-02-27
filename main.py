import os
import string
import random
from flask import Flask, request, render_template_string
import telebot
from telebot import types

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_STORAGE = int(os.getenv("CHANNEL_STORAGE"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")  # pakai @username
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BASE_URL = os.getenv("BASE_URL")  # untuk link web opsional
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= UTIL =================
USERS = {}
FILES = {}  # simpan kode -> message_id

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= INLINE MENU =================
def main_inline():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Start", callback_data="start"),
        types.InlineKeyboardButton("Upload", callback_data="upload")
    )
    markup.row(
        types.InlineKeyboardButton("GetCode", callback_data="getcode"),
        types.InlineKeyboardButton("MyCode", callback_data="mycode")
    )
    markup.row(
        types.InlineKeyboardButton("Notification", callback_data="notification"),
        types.InlineKeyboardButton("ChannelHome", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}")
    )
    markup.row(
        types.InlineKeyboardButton("Akun", callback_data="akun")
    )
    return markup

# ================= CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "start":
        USERS[user_id] = []
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "🔥 Welcome to FileBot Premium\nUpload file dan dapatkan link + code.", reply_markup=main_inline())

    elif call.data == "upload":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "📤 Kirim file/video sekarang.")

    elif call.data == "getcode":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(user_id, "Masukkan kode:")
        bot.register_next_step_handler(msg, process_code)

    elif call.data == "mycode":
        bot.answer_callback_query(call.id)
        files = USERS.get(user_id, [])
        if not files:
            bot.send_message(user_id, "Belum ada file.")
            return
        text = "📁 File kamu:\n\n"
        for f in files:
            text += f"{f}\n"
        bot.send_message(user_id, text)

    elif call.data == "notification":
        bot.answer_callback_query(call.id)
        if user_id != ADMIN_ID:
            bot.send_message(user_id, "❌ Hanya admin.")
            return
        msg = bot.send_message(user_id, "Kirim pesan broadcast:")
        bot.register_next_step_handler(msg, broadcast_message)

    elif call.data == "akun":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, f"🆔 ID: {user_id}\nUsername: @{call.from_user.username}")

# ================= FILE HANDLER =================
@bot.message_handler(content_types=['document', 'video'])
def handle_file(message):
    user_id = message.from_user.id
    code = generate_code()
    forwarded = bot.forward_message(CHANNEL_STORAGE, message.chat.id, message.message_id)
    FILES[code] = forwarded.message_id

    # simpan di user list
    if user_id not in USERS:
        USERS[user_id] = []
    USERS[user_id].append(code)

    if BASE_URL:
        link = f"{BASE_URL}/file/{code}?user_id={user_id}"
    else:
        link = f"Code: {code}"

    bot.reply_to(message, f"✅ File berhasil disimpan permanen!\n\n🔗 {link}\n🔑 Code: {code}")

def process_code(message):
    code = message.text.upper()
    user_id = message.from_user.id
    if code not in FILES:
        bot.reply_to(message, "❌ Code tidak ditemukan")
        return
    msg_id = FILES[code]
    if BASE_URL:
        link = f"{BASE_URL}/file/{code}?user_id={user_id}"
        bot.reply_to(message, f"🔗 {link}")
    else:
        bot.reply_to(message, f"🔑 Code valid: {code}")

def broadcast_message(message):
    text = message.text
    count = 0
    for uid in USERS.keys():
        try:
            bot.send_message(uid, text)
            count += 1
        except:
            continue
    bot.reply_to(message, f"✅ Broadcast terkirim ke {count} user.")

# ================= WEB VIEW =================
HTML_FILE = """
<html>
<head><title>File Viewer</title>
<style>
body{background:#0f172a;color:white;font-family:Arial;text-align:center}
.card{background:#1e293b;margin:20px auto;padding:15px;width:350px;border-radius:15px}
button{padding:10px 20px;border:none;border-radius:8px;background:#3b82f6;color:white}
a{text-decoration:none;color:white}
</style>
</head>
<body>
<h2>🎬 File Viewer</h2>
{% if not joined %}
<div class="card">
<p>⚠️ Wajib join channel</p>
<a href="https://t.me/{{channel}}" target="_blank"><button>Join Channel</button></a><br><br>
<a href="?user_id={{user_id}}"><button>Verify Join</button></a>
</div>
{% else %}
<div class="card">
<p>🔑 Code: {{code}}</p>
<p>👁 {{views}} views</p>
<a href="{{file_url}}" target="_blank"><button>Open File</button></a>
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
    msg_id = FILES.get(code)
    if not msg_id:
        return "File tidak ditemukan"

    joined = is_user_joined(user_id)
    file_url = f"https://t.me/c/{str(CHANNEL_STORAGE).replace('-100','')}/{msg_id}"

    return render_template_string(HTML_FILE,
                                  joined=joined,
                                  channel=FORCE_CHANNEL.replace('@',''),
                                  user_id=user_id,
                                  code=code,
                                  views=0,
                                  file_url=file_url)

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

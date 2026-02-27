import os
import string
import random
from flask import Flask, request
import telebot
from telebot import types
from database import get_connection, init_db

# ========= CONFIG =========
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_STORAGE = int(os.getenv("CHANNEL_STORAGE"))  # -100xxxx
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")  # @username
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BASE_URL = os.getenv("BASE_URL")  # https://yourapp.up.railway.app
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
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
    cur.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()
    cur.close()
    conn.close()

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 Upload", callback_data="upload"),
        types.InlineKeyboardButton("🔎 Get Code", callback_data="getcode"),
    )
    markup.add(
        types.InlineKeyboardButton("📁 My Code", callback_data="mycode"),
        types.InlineKeyboardButton("👤 Akun", callback_data="akun"),
    )
    markup.add(
        types.InlineKeyboardButton("🏠 ChannelHome", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}")
    )
    if ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("📢 Notification", callback_data="notification")
        )
    return markup

# ========= START =========
@bot.message_handler(commands=['start'])
def start(message):
    save_user(message.from_user.id)

    if not is_user_joined(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔔 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}"),
            types.InlineKeyboardButton("✅ Verify Join", callback_data="verify")
        )
        bot.send_message(
            message.chat.id,
            "⚠️ Kamu harus join channel dulu sebelum menggunakan bot.",
            reply_markup=markup
        )
        return

    bot.send_message(
        message.chat.id,
        "🔥 <b>Welcome to FileBot Premium</b>\n\nUpload file & dapatkan link + code.",
        reply_markup=main_menu()
    )

# ========= CALLBACK =========
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id

    if call.data == "verify":
        if is_user_joined(user_id):
            bot.edit_message_text(
                "✅ Verifikasi berhasil!\n\nWelcome 🎉",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=main_menu()
            )
        else:
            bot.answer_callback_query(call.id, "Kamu belum join!", show_alert=True)

    elif call.data == "upload":
        bot.send_message(call.message.chat.id, "📤 Kirim file/video sekarang.")

    elif call.data == "getcode":
        msg = bot.send_message(call.message.chat.id, "Masukkan kode:")
        bot.register_next_step_handler(msg, process_code)

    elif call.data == "mycode":
        show_mycode(call.message)

    elif call.data == "akun":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"👤 <b>Info Akun</b>\n\n🆔 ID: <code>{user_id}</code>"
        )

    elif call.data == "notification":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "Kirim pesan broadcast:")
        bot.register_next_step_handler(msg, send_broadcast)

# ========= FILE HANDLER =========
@bot.message_handler(content_types=['document', 'video'])
def handle_file(message):
    if not is_user_joined(message.from_user.id):
        bot.reply_to(message, "⚠️ Join channel dulu.")
        return

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
        f"✅ <b>File berhasil disimpan permanen!</b>\n\n🔗 {link}\n🔑 Code: <code>{code}</code>"
    )

# ========= PROCESS CODE =========
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
def show_mycode(message):
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
        bot.send_message(message.chat.id, "Belum ada file.")
        return

    text = "📁 <b>File kamu:</b>\n\n"
    for d in data:
        text += f"🔑 <code>{d[0]}</code> | 👁 {d[1]} views\n"

    bot.send_message(message.chat.id, text)

# ========= BROADCAST =========
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

    if is_user_joined(user_id):
        cur.execute("UPDATE files SET views=views+1 WHERE code=%s", (code,))
        conn.commit()

    cur.close()
    conn.close()

    file_url = f"https://t.me/c/{str(CHANNEL_STORAGE).replace('-100','')}/{message_id}"

    return f"""
    <h2>File Viewer</h2>
    <p>Code: {code}</p>
    <p>Views: {views}</p>
    <a href='{file_url}' target='_blank'>Open File</a>
    """

# ========= WEBHOOK =========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "FileBot Webhook Active 🚀"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=PORT)

import os
import json
import string
import random
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_STORAGE = int(os.getenv("CHANNEL_STORAGE"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")  # pakai @username
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"

# ========= UTIL =========
def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Start", "Upload")
    markup.row("GetCode", "MyCode")
    markup.row("Notification")
    return markup

# ========= START =========
@bot.message_handler(commands=['start'])
def start_command(message):
    args = message.text.split()

    # Jika start dengan code
    if len(args) > 1:
        code = args[1].upper()
        data = load_data()

        if code not in data:
            bot.reply_to(message, "❌ Code tidak ditemukan.")
            return

        if not is_user_joined(message.from_user.id):
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔔 Join Channel",
                    url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}"
                )
            )
            bot.reply_to(
                message,
                "⚠️ Kamu harus join channel dulu!",
                reply_markup=markup
            )
            return

        message_id = data[code]

        bot.copy_message(
            message.chat.id,
            CHANNEL_STORAGE,
            message_id
        )
        return

    bot.send_message(
        message.chat.id,
        "🔥 Welcome to FileBot\nUpload file dan dapatkan link + code.",
        reply_markup=main_menu()
    )

# ========= UPLOAD =========
@bot.message_handler(func=lambda m: m.text == "Upload")
def upload_info(message):
    bot.send_message(message.chat.id, "📤 Kirim file/video sekarang.")

@bot.message_handler(content_types=['document', 'video'])
def handle_file(message):
    code = generate_code()

    forwarded = bot.forward_message(
        CHANNEL_STORAGE,
        message.chat.id,
        message.message_id
    )

    data = load_data()
    data[code] = forwarded.message_id
    save_data(data)

    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={code}"

    bot.reply_to(
        message,
        f"✅ File berhasil disimpan permanen!\n\n"
        f"🔗 {link}\n"
        f"🔑 Code: {code}"
    )

# ========= GET CODE =========
@bot.message_handler(func=lambda m: m.text == "GetCode")
def ask_code(message):
    msg = bot.send_message(message.chat.id, "Masukkan kode:")
    bot.register_next_step_handler(msg, process_code)

def process_code(message):
    code = message.text.upper()
    data = load_data()

    if code not in data:
        bot.reply_to(message, "❌ Code tidak ditemukan.")
        return

    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={code}"

    bot.reply_to(message, f"🔗 {link}")

# ========= MY CODE =========
@bot.message_handler(func=lambda m: m.text == "MyCode")
def my_code(message):
    data = load_data()

    user_codes = []
    for code, msg_id in data.items():
        user_codes.append(code)

    if not user_codes:
        bot.reply_to(message, "Belum ada file.")
        return

    text = "📁 Semua Code:\n\n"
    for c in user_codes:
        text += f"{c}\n"

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
    bot.reply_to(message, "⚠️ Versi tanpa database tidak support broadcast massal.")

# ========= RUN =========
bot.infinity_polling()

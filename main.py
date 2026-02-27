import os
import json
import string
import random
import telebot
from telebot import types

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_STORAGE = int(os.getenv("CHANNEL_STORAGE"))  # contoh: -100xxxxxxxxxx
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")  # contoh: @namachannel
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "data.json"

# ================= UTIL =================

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_joined(user_id):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 Upload", callback_data="upload"),
        types.InlineKeyboardButton("🔑 GetCode", callback_data="getcode")
    )
    markup.add(
        types.InlineKeyboardButton("📁 MyCode", callback_data="mycode"),
        types.InlineKeyboardButton("👤 Akun", callback_data="account")
    )
    markup.add(
        types.InlineKeyboardButton(
            "🏠 ChannelHome",
            url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}"
        )
    )
    return markup

# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()

    # Jika start dengan code
    if len(args) > 1:
        code = args[1].upper()
        data = load_data()

        if code not in data:
            bot.reply_to(message, "❌ Code tidak valid.")
            return

        if not is_joined(message.from_user.id):
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔔 Join Channel",
                    url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}"
                )
            )
            bot.reply_to(
                message,
                "⚠️ Kamu wajib join channel dulu!",
                reply_markup=markup
            )
            return

        msg_id = data[code]

        bot.copy_message(
            message.chat.id,
            CHANNEL_STORAGE,
            msg_id
        )
        return

    bot.send_message(
        message.chat.id,
        f"🔥 Welcome {message.from_user.first_name}\n\n"
        "Upload file dan dapatkan link + code premium.",
        reply_markup=main_menu()
    )

# ================= CALLBACK =================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "upload":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📤 Kirim file/video sekarang.")

    elif call.data == "getcode":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Masukkan kode:")
        bot.register_next_step_handler(msg, process_code)

    elif call.data == "mycode":
        bot.answer_callback_query(call.id)
        data = load_data()

        if not data:
            bot.send_message(call.message.chat.id, "Belum ada file.")
            return

        text = "📁 Semua Code:\n\n"
        for c in data.keys():
            text += f"{c}\n"

        bot.send_message(call.message.chat.id, text)

    elif call.data == "account":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"👤 AKUN INFO\n\n"
            f"ID: {user_id}\n"
            f"Nama: {call.from_user.first_name}"
        )

# ================= FILE UPLOAD =================

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

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Open Link", url=link))

    bot.reply_to(
        message,
        f"✅ File berhasil disimpan permanen!\n\n"
        f"🔑 Code: `{code}`\n"
        f"🔗 Link: {link}",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ================= PROCESS CODE =================

def process_code(message):
    code = message.text.upper()
    data = load_data()

    if code not in data:
        bot.reply_to(message, "❌ Code tidak ditemukan.")
        return

    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={code}"

    bot.reply_to(message, f"🔗 {link}")

# ================= RUN =================

print("Bot Running...")
bot.infinity_polling()

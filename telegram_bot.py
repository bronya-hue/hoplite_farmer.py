import telebot
import subprocess
import os
import threading
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

CONFIG_FILE = "config.json"
is_farming = False

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(key, value):
    config = load_config()
    config[key] = value
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "🤖 *Hoplite Auto-Farmer Bot*\n\n"
        "🛠 *Pengaturan:*\n"
        "`/setproxy` - Atur Proxy (Wajib untuk Railway)\n"
        "`/setpromo` - Atur Kode Promo (Default: CLOUDFIRST)\n\n"
        "🚀 *Aksi:*\n"
        "`/farm` - Mulai buat 1 akun Hoplite\n"
        "`/status` - Cek pengaturan & status bot"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['setproxy'])
def ask_proxy(message):
    msg = bot.reply_to(message, "🔗 Kirimkan URL Proxy Anda.\nContoh: `http://user:pass@ip:port`\nKetik `-` jika ingin tanpa proxy (Risiko diblokir).", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_proxy)

def save_proxy(message):
    proxy_url = message.text.strip()
    if proxy_url == "-":
        proxy_url = ""
    save_config("PROXY_URL", proxy_url)
    bot.reply_to(message, "✅ Proxy berhasil disimpan!")

@bot.message_handler(commands=['setpromo'])
def ask_promo(message):
    msg = bot.reply_to(message, "🎟 Kirimkan Kode Promo Hoplite Anda.\nContoh: `CLOUDFIRST`")
    bot.register_next_step_handler(msg, save_promo)

def save_promo(message):
    promo_code = message.text.strip()
    save_config("HOPLITE_PROMO", promo_code)
    bot.reply_to(message, f"✅ Kode promo `{promo_code}` berhasil disimpan!", parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def check_status(message):
    global is_farming
    config = load_config()
    
    status_text = "📊 *Status Bot*\n\n"
    status_text += f"🔄 Farming: {'⏳ Berjalan' if is_farming else '✅ Idle'}\n\n"
    status_text += "⚙️ *Konfigurasi Tersimpan:*\n"
    
    proxy = config.get("PROXY_URL", "Belum diset ❌")
    if proxy and len(proxy) > 15:
        proxy = proxy[:10] + "..." + proxy[-5:]
    status_text += f"🌐 Proxy: `{proxy if proxy else 'Tanpa Proxy'}`\n"
    
    promo = config.get("HOPLITE_PROMO", "CLOUDFIRST (Default)")
    status_text += f"🎟 Promo: `{promo}`\n"

    bot.reply_to(message, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['farm'])
def start_farming(message):
    global is_farming
    if is_farming:
        bot.reply_to(message, "❌ Proses farming sedang berjalan! Tunggu hingga selesai.")
        return
    
    is_farming = True
    msg = bot.reply_to(message, "⏳ Memulai farming Hoplite...\nMendaftar, verifikasi email, dan redeem promo. (1-2 Menit)")
    
    thread = threading.Thread(target=run_farm_script, args=(message.chat.id, msg.message_id))
    thread.start()

def run_farm_script(chat_id, message_id):
    global is_farming
    config = load_config()
    
    try:
        env_vars = os.environ.copy()
        if config.get("PROXY_URL"):
            env_vars["PROXY_URL"] = config["PROXY_URL"]
        if config.get("HOPLITE_PROMO"):
            env_vars["HOPLITE_PROMO"] = config["HOPLITE_PROMO"]

        # Jalankan skrip Playwright
        process = subprocess.run(
            ["python", "scripts/hoplite_farmer.py"], 
            capture_output=True, 
            text=True,
            timeout=300,
            env=env_vars
        )
        
        output = process.stdout
        error = process.stderr
        
        if process.returncode == 0:
            result_text = f"✅ *Hoplite Farming Selesai!*\n\nLog:\n`{output[-600:]}`"
        else:
            result_text = f"❌ *Hoplite Gagal*\n\nError:\n`{error[-600:]}`"
            
    except subprocess.TimeoutExpired:
        result_text = "❌ *Error:* Proses farming melebihi batas waktu (5 menit)."
    except Exception as e:
        result_text = f"❌ *Error Sistem:* {str(e)}"
    finally:
        is_farming = False
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            parse_mode='Markdown'
        )

if __name__ == '__main__':
    print("Bot Telegram berjalan...")
    bot.infinity_polling()

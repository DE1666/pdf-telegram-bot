import os
import json
import logging
from io import BytesIO
from PIL import Image
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, ContextTypes, filters
)

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration & Constants
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 6071687483  # Your Telegram User ID
DATA_FILE = "data/users.json"

# Helper functions for data persistence
def load_data():
    if not os.path.exists("data"):
        os.makedirs("data")
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"users": {}, "total_pdfs": 0}
    return {"users": {}, "total_pdfs": 0}

def save_data(data):
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

db = load_data()

def register_user(user_id, username):
    str_id = str(user_id)
    if str_id not in db["users"]:
        db["users"][str_id] = {
            "username": username,
            "is_vip": False,
            "pdfs_created": 0,
            "referrals": 0
        }
        save_data(db)

# Main Menu Keyboard
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🖼️ تحويل الصورة إلى PDF", callback_data="convert_pdf")],
        [InlineKeyboardButton("🔗 رابط الإحالة الخاص بي", callback_data="my_ref"), InlineKeyboardButton("📊 رصيدي", callback_data="my_stats")],
        [InlineKeyboardButton("⭐ الحصول على VIP (100 نجمة)", callback_data="buy_vip")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    
    welcome_text = (
        f"مرحباً بك {user.first_name} في بوت أدوات الصور وPDF! 🚀\n\n"
        "اختر إجراءً من القائمة أدناه، أو أرسل صورة فوراً لتحويلها إلى PDF:"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

# Callback Handler
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    str_id = str(user_id)

    if query.data == "convert_pdf":
        await query.edit_message_text("من فضلك قم بإرسال الصورة الآن ليتم تحويلها مباشرة إلى PDF.")
    
    elif query.data == "my_ref":
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        refs_count = db["users"].get(str_id, {}).get("referrals", 0)
        await query.edit_message_text(
            f"🔗 **رابط الإحالة الخاص بك:**\n{ref_link}\n\n"
            f"👥 عدد الدعوات الناجحة: {refs_count}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("العودة للقائمة", callback_data="main_menu")]])
        )

    elif query.data == "my_stats":
        user_data = db["users"].get(str_id, {})
        vip_status = "👑 VIP (مفعل)" if user_data.get("is_vip") else "🔒 حساب عادي"
        pdfs = user_data.get("pdfs_created", 0)
        await query.edit_message_text(
            f"📊 **بيانات حسابك:**\n\n"
            f"الحالة: {vip_status}\n"
            f"عدد ملفات PDF المنشأة: {pdfs}\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("العودة للقائمة", callback_data="main_menu")]])
        )

    elif query.data == "buy_vip":
        # Send Telegram Stars Invoice
        title = "اشتراك VIP لمدة 30 يوماً"
        description = "احصل على ميزات VIP وأولوية في تحويل الملفات وبدون قيود!"
        payload = f"vip_sub_{user_id}"
        currency = "XTR"  # Telegram Stars Currency
        prices = [LabeledPrice("اشتراك VIP", 100)]  # 100 Stars

        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Must be empty for Telegram Stars (XTR)
            currency=currency,
            prices=prices
        )

    elif query.data == "main_menu":
        await query.edit_message_text("اختر إجراءً من القائمة أدناه:", reply_markup=main_keyboard())

# Telegram Stars Pre-Checkout & Payment Handling
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("vip_sub_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="حدث خطأ في طلب الدفع.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    if str_id in db["users"]:
        db["users"][str_id]["is_vip"] = True
        save_data(db)
    
    await update.message.reply_text(
        "🎉 **تم الدفع بنجاح!**\nتم تفعيل اشتراك VIP بحسابك بنجاح. شكراً لدعمك!"
    )

# Photo to PDF Conversion
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    
    msg = await update.message.reply_text("⏳ جاري تحويل الصورة إلى PDF...")
    
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    pdf_output = BytesIO()
    image.save(pdf_output, format="PDF")
    pdf_output.seek(0)
    
    # Update Stats
    str_id = str(user.id)
    db["users"][str_id]["pdfs_created"] = db["users"][str_id].get("pdfs_created", 0) + 1
    db["total_pdfs"] = db.get("total_pdfs", 0) + 1
    save_data(db)
    
    await msg.delete()
    await update.message.reply_document(
        document=pdf_output,
        filename=f"converted_{user.id}.pdf",
        caption="✅ تم تحويل الصورة بنجاح!"
    )

# Admin Panel Commands (/admin, /broadcast)
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    total_users = len(db["users"])
    total_pdfs = db.get("total_pdfs", 0)
    vip_users = sum(1 for u in db["users"].values() if u.get("is_vip"))
    
    admin_text = (
        "👑 **لوحة تحكم الأدمن**\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"⭐ مستخدمي VIP: `{vip_users}`\n"
        f"📄 إجمالي ملفات PDF المرفوعة: `{total_pdfs}`\n\n"
        "📢 لإرسال إذاعة لجميع المستخدمين استخدم الأمر:\n`/broadcast نص الرسالة`"
    )
    await update.message.reply_text(admin_text, parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ يرجى كتابة الرسالة بعد الأمر، مثال:\n`/broadcast مرحباً بالجميع`", parse_mode="Markdown")
        return
    
    broadcast_msg = " ".join(context.args)
    success = 0
    failed = 0
    
    await update.message.reply_text("⏳ جاري إرسال الإذاعة للجميع...")
    
    for uid in list(db["users"].keys()):
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_msg)
            success += 1
        except Exception:
            failed += 1
            
    await update.message.reply_text(f"✅ اكتملت الإذاعة!\n\nنجاح: {success}\nفشل: {failed}")

# Main Application Entrypoint
def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Payment Handlers
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = "8616066471:AAEqGInkhiIVRMUbUTZYLd3TuVdBKjGKwCQ"
MANAGER_ID = 7879728258  # сюда ID менеджера

# товары с ценой
PRODUCTS = {
    "без газа 0,33": 3000,
    "без газа 0,5": 5000,
    "без газа 1": 8000,
    "без газа 1,5": 12000,
    "без газа 5": 35000,
    "без газа 10": 65000,
    "с газом 0,5": 5500,
    "с газом 1": 9000,
    "с газом 1,5": 13000,
}

user_orders = {}             # текущие заказы
user_current_product = {}    # какой товар выбирает агент для ввода количества

# старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🆕 Создать заказ"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# создать заказ
async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_orders[user_id] = {}
    await show_products(update, context, user_id, "Выбирай товары:")

# показать товары
async def show_products(update, context, user_id, text_msg):
    keyboard = []
    for product in PRODUCTS:
        keyboard.append([InlineKeyboardButton(product, callback_data=product)])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done")])

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard))

# обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "done":
        order = user_orders.get(user_id, {})
        if not order:
            await query.message.reply_text("❌ Ты ничего не выбрал")
            return
        # запрос геолокации
        kb = [[KeyboardButton("📍 Отправить локацию", request_location=True)]]
        await query.message.reply_text(
            "Отправь геолокацию для завершения заказа:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return

    # выбран товар → запоминаем и спрашиваем количество
    product = query.data
    user_current_product[user_id] = product
    await query.message.reply_text(f"Введите количество для {product}:")

# обработка текста (количество или команды)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # если агент вводит количество для выбранного товара
    if user_id in user_current_product:
        product = user_current_product[user_id]
        try:
            qty = int(update.message.text)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число больше 0")
            return

        user_orders[user_id][product] = user_orders[user_id].get(product, 0) + qty
        del user_current_product[user_id]

        await update.message.reply_text(f"{product} x{qty} добавлен в заказ")
        await show_products(update, context, user_id, "Можно выбрать ещё товары или нажать ✅ Готово")
        return

# обработка локации
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    loc = update.message.location
    location_text = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    await send_order(update, context, location_text)

# отправка менеджеру
async def send_order(update, context, address):
    user_id = update.effective_user.id
    order = user_orders.get(user_id, {})
    if not order:
        await update.message.reply_text("❌ Заказ пуст")
        return

    total = sum(PRODUCTS[p] * qty for p, qty in order.items() if qty > 0)
    agent_name = update.effective_user.first_name

    text = f"🆕 Новый заказ\n👤 Агент: {agent_name}\n\n📦 Товары:\n"
    for p, qty in order.items():
        if qty > 0:
            text += f"- {p} x{qty} = {PRODUCTS[p]*qty}\n"
    text += f"\n💰 Итого: {total}\n📍 Адрес: {address}"

    await context.bot.send_message(chat_id=MANAGER_ID, text=text)
    await update.message.reply_text("✅ Заказ отправлен менеджеру")

    # сброс заказа и возможность создать новый
    user_orders[user_id] = {}
    keyboard = [["🆕 Создать заказ"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Можно создать новый заказ:", reply_markup=reply_markup)

# запуск бота
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🆕 Создать заказ"), create_order))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.LOCATION, handle_location))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.run_polling()
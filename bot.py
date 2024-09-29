PORT', 5000)))
import logging
import os
import subprocess
import importlib
import sys
import json
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, ApplicationBuilder, ContextTypes

# BOT OWNER SETTINGS
OWNER_ID = 1159381624  # Your ID here
LOG_CHANNEL_ID = -100123456789  # Your private log channel ID
JOIN_LEAVE_LOG_CHANNEL = -100987654321  # GC for join/leave logs
BAN_LOG_CHANNEL = -100111222333  # GC for ban logs
LOG_FILE = "bot.log"
PLUGINS_FOLDER = "plugins/"
HELP_REGISTRY = {}

# Initialize Flask app
app = Flask(__name__)

# Initialize logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check if plugins folder exists
if not os.path.exists(PLUGINS_FOLDER):
    os.makedirs(PLUGINS_FOLDER)

# Utility: Check if user is the bot owner
def owner_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != OWNER_ID:
            await update.message.reply_text("This command is restricted to the bot owner.")
            return
        return await func(update, context)
    return wrapper

# /start Command for normal users
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm a group management bot!")

# /dev Command for bot owner
@owner_only
async def dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Developer mode active. Use /devhelp for all commands.")

# /devhelp: Lists all available developer commands
@owner_only
async def dev_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
    /install - Install a plugin.
    /uninstall - Uninstall a plugin.
    /export - Export installed plugins.
    /log - Get the bot's logs.
    /reset - Reset bot data.
    /restart - Restart the bot.
    /leave <chat_id> - Force bot to leave a chat.
    """
    await update.message.reply_text(commands)

# /install: Reply to a Python file to install as a plugin
@owner_only
async def install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("Please reply to a Python file to install.")
        return

    doc = message.reply_to_message.document
    if doc.file_name.endswith(".py"):
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(os.path.join(PLUGINS_FOLDER, doc.file_name))

        # Import the plugin dynamically
        plugin_name = doc.file_name[:-3]
        try:
            importlib.import_module(f"plugins.{plugin_name}")
            await message.reply_text(f"Plugin {plugin_name} installed successfully!")
            # Update help dynamically
            add_help(plugin_name)
        except Exception as e:
            await message.reply_text(f"Failed to install {plugin_name}: {str(e)}")
            os.remove(os.path.join(PLUGINS_FOLDER, doc.file_name))

        # Install requirements (if any)
        install_requirements(os.path.join(PLUGINS_FOLDER, doc.file_name))
    else:
        await message.reply_text("Only .py files are allowed for plugin installation.")

# Install requirements from requirements.txt if present
def install_requirements(plugin_path):
    req_file = plugin_path.replace(".py", ".txt")  # Assuming requirements.txt is named plugin.txt
    if os.path.exists(req_file):
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])

# Uninstall a plugin by name or command
@owner_only
async def uninstall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        plugin_name = context.args[0]
        if os.path.exists(f"{PLUGINS_FOLDER}{plugin_name}.py"):
            os.remove(f"{PLUGINS_FOLDER}{plugin_name}.py")
            await update.message.reply_text(f"Plugin {plugin_name} uninstalled.")
            remove_help(plugin_name)
        else:
            await update.message.reply_text(f"Plugin {plugin_name} not found.")
    except IndexError:
        await update.message.reply_text("Please provide the plugin name to uninstall.")

# Export installed plugins
@owner_only
async def export_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = os.listdir(PLUGINS_FOLDER)
    for f in files:
        await update.message.reply_document(open(os.path.join(PLUGINS_FOLDER, f), "rb"))

# /log: Send bot logs to the owner
@owner_only
async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(LOG_FILE, "rb") as log_file:
        await context.bot.send_document(chat_id=OWNER_ID, document=log_file)

# Add help dynamically
def add_help(plugin_name):
    # Assuming plugins have a 'help' attribute for help text
    plugin = importlib.import_module(f"plugins.{plugin_name}")
    HELP_REGISTRY[plugin_name] = plugin.help

# Remove help dynamically
def remove_help(plugin_name):
    if plugin_name in HELP_REGISTRY:
        del HELP_REGISTRY[plugin_name]

# /help: Display help information dynamically based on installed plugins
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for category in HELP_REGISTRY:
        keyboard.append([InlineKeyboardButton(category, callback_data=category)])
    await update.message.reply_text("Choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))

# Callback handler to display help content
async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    help_text = HELP_REGISTRY.get(category, "No help available for this category.")
    await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Reset command to reset bot cache and data
@owner_only
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot reset successfully!")
    # Add logic to reset bot data

# Restart command to restart the bot
@owner_only
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# Notify owner on start or restart
async def notify_owner_start(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(OWNER_ID, "Bot has started successfully!")

# Define a route for webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    app.dispatcher.process_update(update)
    return 'ok'

# Main function to start the bot
async def main():
    application = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("dev", dev))
    application.add_handler(CommandHandler("devhelp", dev_help))
    application.add_handler(CommandHandler("install", install))
    application.add_handler(CommandHandler("uninstall", uninstall))
    application.add_handler(CommandHandler("export", export_plugins))
    application.add_handler(CommandHandler("log", get_logs))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(help_callback))

    # Notify owner when the bot starts
    application.job_queue.run_once(notify_owner_start, 0)

    # Start the bot with webhook
    await application.start_webhook(listen="0.0.0.0",
                                     port=int(os.environ.get('PORT', 8443)),
                                     url_path='webhook')
    application.bot.set_webhook(url='https://<your-koyeb-url>/webhook')

    # Start Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

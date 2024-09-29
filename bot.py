import logging
import os
import subprocess
import importlib
import sys
from flask import Flask, request
from telegram import Update, ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, Dispatcher
from functools import wraps
from telegram import Bot

# BOT OWNER SETTINGS
OWNER_ID = 1159381624  # Your ID here
LOG_FILE = "bot.log"
PLUGINS_FOLDER = "plugins/"
HELP_REGISTRY = {}

# Initialize Flask app
app = Flask(__name__)

# Initialize logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name)

# Initialize the Telegram bot
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
bot = Bot(token=TOKEN)

# Check if plugins folder exists
if not os.path.exists(PLUGINS_FOLDER):
    os.makedirs(PLUGINS_FOLDER)

# Initialize Dispatcher
dispatcher = Dispatcher(bot, None)

# Utility: Check if user is the bot owner
def owner_only(func):
    @wraps(func)
    def wrapper(update: Update, context):
        user_id = update.effective_user.id
        if user_id != OWNER_ID:
            update.message.reply_text("This command is restricted to the bot owner.")
            return
        return func(update, context)
    return wrapper

# /start Command for normal users
def start(update, context):
    update.message.reply_text("Hello! I'm a group management bot!")

# /dev Command for bot owner
@owner_only
def dev(update, context):
    update.message.reply_text("Developer mode active. Use /devhelp for all commands.")

# /devhelp: Lists all available developer commands
@owner_only
def dev_help(update, context):
    commands = """
    /install - Install a plugin.
    /uninstall - Uninstall a plugin.
    /export - Export installed plugins.
    /log - Get the bot's logs.
    /reset - Reset bot data.
    /restart - Restart the bot.
    /leave <chat_id> - Force bot to leave a chat.
    """
    update.message.reply_text(commands)

# /install: Reply to a Python file to install as a plugin
@owner_only
def install(update, context):
    message = update.message
    if not message.reply_to_message or not message.reply_to_message.document:
        message.reply_text("Please reply to a Python file to install.")
        return

    doc = message.reply_to_message.document
    if doc.file_name.endswith(".py"):
        file = context.bot.get_file(doc.file_id)
        file.download(PLUGINS_FOLDER + doc.file_name)

        # Import the plugin dynamically
        plugin_name = doc.file_name[:-3]
        try:
            importlib.import_module(f"plugins.{plugin_name}")
            message.reply_text(f"Plugin {plugin_name} installed successfully!")
            # Update help dynamically
            add_help(plugin_name)
        except Exception as e:
            message.reply_text(f"Failed to install {plugin_name}: {str(e)}")
            os.remove(PLUGINS_FOLDER + doc.file_name)

        # Install requirements (if any)
        install_requirements(PLUGINS_FOLDER + doc.file_name)
    else:
        message.reply_text("Only .py files are allowed for plugin installation.")

# Install requirements from requirements.txt if present
def install_requirements(plugin_path):
    req_file = plugin_path.replace(".py", ".txt")  # Assuming requirements.txt is named plugin.txt
    if os.path.exists(req_file):
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])

# Uninstall a plugin by name or command
@owner_only
def uninstall(update, context):
    try:
        plugin_name = context.args[0]
        if os.path.exists(f"{PLUGINS_FOLDER}{plugin_name}.py"):
            os.remove(f"{PLUGINS_FOLDER}{plugin_name}.py")
            update.message.reply_text(f"Plugin {plugin_name} uninstalled.")
            remove_help(plugin_name)
        else:
            update.message.reply_text(f"Plugin {plugin_name} not found.")
    except IndexError:
        update.message.reply_text("Please provide the plugin name to uninstall.")

# Export installed plugins
@owner_only
def export_plugins(update, context):
    files = os.listdir(PLUGINS_FOLDER)
    for f in files:
        update.message.reply_document(open(PLUGINS_FOLDER + f, "rb"))

# /log: Send bot logs to the owner
@owner_only
def get_logs(update, context):
    with open(LOG_FILE, "rb") as log_file:
        context.bot.send_document(chat_id=OWNER_ID, document=log_file)

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
def help_command(update, context):
    keyboard = []
    for category in HELP_REGISTRY:
        keyboard.append([InlineKeyboardButton(category, callback_data=category)])
    update.message.reply_text("Choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))

# Callback handler to display help content
def help_callback(update, context):
    query = update.callback_query
    query.answer()
    category = query.data
    help_text = HELP_REGISTRY.get(category, "No help available for this category.")
    query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Reset command to reset bot cache and data
@owner_only
def reset(update, context):
    update.message.reply_text("Bot reset successfully!")
    # Add logic to reset bot data

# Restart command to restart the bot
@owner_only
def restart(update, context):
    update.message.reply_text("Bot restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# Webhook handler
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Set the webhook
def set_webhook():
    webhook_url = "https://chronic-annette-xexa-e31683de.koyeb.app/webhook"  # Replace with your Koyeb URL
    bot.setWebhook(webhook_url)

# Start Flask app
if __name__ == "__main__":
    # Set the webhook first
    set_webhook()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

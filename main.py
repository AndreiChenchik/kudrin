import os
import logging

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
TOKEN = os.environ['TOKEN']

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

def caps(update, context):
    text_caps = ' '.join(context.args).upper()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)

def recalculate_balance(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,text='TBD')

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), echo))
    dp.add_handler(CommandHandler('caps', caps))
    dp.add_handler(CommandHandler('recalculate_balance', recalculate_balance))

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
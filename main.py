import os
import logging
from notion.client import NotionClient
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# settings
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
NOTION_TOKEN = os.environ['NOTION_TOKEN']
LIMIT = os.environ['CREDIT_LIMIT']
POWER_USER_ID = int(os.environ['POWER_USER_ID'])
POWER_USER_NAME = os.environ['POWER_USER_NAME']

notion_balance = "https://www.notion.so/chenchiks/2062899533a048579f572a7e3d40182f?v=1fb6c93b1a5045af9ea3a83b4aa90dd0"
notion_transactions = "https://www.notion.so/chenchiks/1604cc3bb0614273a690710f17b138ca?v=8f278effcac4457d803aeb5cc0a1c93e"
credit_limit = int(LIMIT)

recalculate = "Recalculate"
newlink = "Update numbers"
recalculate_keyboard = KeyboardButton(text=recalculate)
link_keyboard = KeyboardButton(text=newlink)
custom_keyboard = [[recalculate_keyboard, link_keyboard]]
reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)

newlink_filter = Filters.text([newlink]) & (
            Filters.user(user_id=POWER_USER_ID) | Filters.user(username=POWER_USER_NAME))
recalculate_filter = Filters.text([recalculate]) & (
            Filters.user(user_id=POWER_USER_ID) | Filters.user(username=POWER_USER_NAME))
in_known_filters = newlink_filter | recalculate_filter | Filters.command('start')


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!",
                             reply_markup=reply_markup)


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm sorry Dave I'm afraid I can't do that.",
                             reply_markup=reply_markup)


def daily_status(day, date, planned_month, daily):
    return (
            planned_month[planned_month["transaction_time"] <= date][
                "transaction_amount"
            ].sum()
            - (day + 1) * daily
    )


def transactions_left(date, planned_month):
    return planned_month[planned_month["transaction_time"] > date][
        "transaction_amount"
    ].sum()


def transactions_made(date, planned_month):
    return planned_month[planned_month["transaction_time"] <= date][
        "transaction_amount"
    ].sum()


def generate_link(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="5 sec")
    now = pd.Timestamp(datetime.now().timestamp(), unit="s").to_period(freq="M")
    month = now

    client = NotionClient(token_v2=NOTION_TOKEN)
    cv = client.get_collection_view(notion_balance)
    notion_data = [[row.id, row.date.start, row.credit, row.cash, row.usd] for row in cv.collection.get_rows()]
    balance = pd.DataFrame(notion_data, columns=['id', 'balance_time', 'Credit', 'Cash', 'USD'])

    balance["balance_year"] = balance["balance_time"].dt.to_period("Y").dt.start_time
    balance["balance_month"] = balance["balance_time"].dt.to_period("M").dt.start_time
    balance["balance_day"] = balance["balance_time"].dt.to_period("D").dt.start_time
    balance["balance_week"] = balance["balance_day"] - balance[
        "balance_day"
    ].dt.weekday * np.timedelta64(1, "D")

    yf_exchange = (
        (yf.Ticker("RUB=X")
         .history(period="max")["Close"]
         .reset_index()
         .rename({"index": "date"}, axis=1))
    )
    exchange = pd.DataFrame(
        pd.date_range(start=month.start_time, end=month.end_time)
    ).rename({0: "date"}, axis=1)
    exchange["usd_rate"] = exchange["date"].apply(
        lambda x: yf_exchange[yf_exchange["Date"] <= x].iloc[-1]["Close"]
    )

    balance = balance.merge(exchange, left_on="balance_day", right_on="date")

    balance["Business"] = (
            balance["USD"] * balance["usd_rate"]
    )

    balance["balance"] = (
            balance["Credit"] - credit_limit + balance["Cash"] + balance["Business"]
    )

    latest_balance = balance.sort_values(by='balance_time').iloc[-1]

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f"*Please fill in* [Balance form](https://docs.google.com/forms/d/e/1FAIpQLSe8JaUuKA22qdeun1MtOUK21LkxXjdcu-yJPUjri-T4Y7m60g/viewform?usp=pp_url&entry.910435313={latest_balance['Credit']}&entry.2073871224={latest_balance['Cash']}&entry.1266770758={latest_balance['USD']}) and after that ask me to recalculate the balance",
                             parse_mode=ParseMode.MARKDOWN)


def recalculate_balance(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Uno momento!")
    # настроим отображение дробных величин
    pd.options.display.float_format = "{:,.2f}".format

    # настроим размеры графиков (пришлось вынести в отдельный блок, т.к. иначе оно не работает)
    sns.set(
        context="notebook", style="whitegrid", rc={"figure.figsize": (15, 9)},
    )
    plt.style.use("seaborn-muted")

    # get info about this month
    now = pd.Timestamp(datetime.now().timestamp(), unit="s").to_period(freq="M")
    month = now
    days_in_month = month.days_in_month

    client = NotionClient(token_v2=NOTION_TOKEN)
    cv = client.get_collection_view(notion_balance)
    notion_data = [[row.id, row.date.start, row.credit, row.cash, row.usd] for row in cv.collection.get_rows()]
    balance = pd.DataFrame(notion_data, columns=['id', 'balance_time', 'Credit', 'Cash', 'USD'])

    cv = client.get_collection_view(notion_transactions)
    notion_data = [[row.id, row.date.start, row.amount] for row in cv.collection.get_rows()]
    planned = pd.DataFrame(notion_data, columns=['id', 'Date', 'transaction_amount'])

    balance["balance_year"] = balance["balance_time"].dt.to_period("Y").dt.start_time
    balance["balance_month"] = balance["balance_time"].dt.to_period("M").dt.start_time
    balance["balance_day"] = balance["balance_time"].dt.to_period("D").dt.start_time
    balance["balance_week"] = balance["balance_day"] - balance[
        "balance_day"
    ].dt.weekday * np.timedelta64(1, "D")

    yf_exchange = (
        (yf.Ticker("RUB=X")
            .history(period="max")["Close"]
            .reset_index()
            .rename({"index": "date"}, axis=1))
    )
    exchange = pd.DataFrame(
        pd.date_range(start=month.start_time, end=month.end_time)
    ).rename({0: "date"}, axis=1)
    exchange["usd_rate"] = exchange["date"].apply(
        lambda x: yf_exchange[yf_exchange["Date"] <= x].iloc[-1]["Close"]
    )

    balance = balance.merge(exchange, left_on="balance_day", right_on="date")

    balance["Business"] = (
            balance["USD"] * balance["usd_rate"]
    )

    balance["balance"] = (
            balance["Credit"] - credit_limit + balance["Cash"] + balance["Business"]
    )

    balance_daily = balance.sort_values(by='balance_time')[["balance_day", "balance"]].drop_duplicates(
        subset="balance_day", keep="last"
    )

    planned["transaction_time"] = pd.to_datetime(planned["Date"])

    planned["transaction_year"] = (
        planned["transaction_time"].dt.to_period("Y").dt.start_time
    )
    planned["transaction_month"] = (
        planned["transaction_time"].dt.to_period("M").dt.start_time
    )
    planned["transaction_day"] = planned["transaction_time"].dt.to_period("D").dt.start_time
    planned["transaction_week"] = planned["transaction_day"] - planned[
        "transaction_day"
    ].dt.weekday * np.timedelta64(1, "D")

    planned_month = planned[planned["transaction_month"] == month.start_time]

    monthly_chart = (
        pd.DataFrame(index=pd.date_range(start=month.start_time, end=month.end_time))
            .reset_index()
            .reset_index()
            .rename({"index": "date", "level_0": "day"}, axis=1)
    )

    daily = planned_month["transaction_amount"].sum() / days_in_month

    monthly_chart["planned"] = monthly_chart.apply(
        lambda row: daily_status(row["day"], row["date"], planned_month, daily), axis=1
    )

    monthly_chart["transactions_left"] = monthly_chart.apply(
        lambda row: transactions_left(row["date"], planned_month), axis=1
    )

    monthly_chart["transactions_made"] = monthly_chart.apply(
        lambda row: transactions_made(row["date"], planned_month), axis=1
    )

    monthly_chart = (
        monthly_chart[["date", "planned", "transactions_left", "transactions_made"]]
            .merge(balance_daily, how="left", left_on="date", right_on="balance_day")
            .drop(["balance_day"], axis=1)
    )
    monthly_chart["planned_diff"] = monthly_chart["balance"] - monthly_chart["planned"]
    monthly_chart["misc"] = (
            monthly_chart["transactions_made"] + monthly_chart["transactions_left"]
    )
    monthly_chart["daily_spent"] = (
            monthly_chart["transactions_made"] - monthly_chart["balance"]
    )
    monthly_chart["day"] = monthly_chart["date"].dt.day
    monthly_chart["days_left"] = days_in_month - monthly_chart["day"]
    monthly_chart["new_daily"] = (
                                         monthly_chart["balance"] + monthly_chart["transactions_left"]
                                 ) / monthly_chart["days_left"]
    monthly_chart["avg_daily"] = daily

    monthly_chart = monthly_chart.merge(
        monthly_chart.dropna(subset=["balance"]).shift(1)["new_daily"].rename("old_daily"),
        how="left",
        left_index=True,
        right_index=True,
    ).merge(
        monthly_chart.dropna(subset=["balance"]).diff()["day"].rename("days_after"),
        how="left",
        left_index=True,
        right_index=True,
    ).merge(monthly_chart.dropna(subset=["balance"]).diff()["daily_spent"].rename("daily_spent_diff"),
            how="left",
            left_index=True,
            right_index=True)

    monthly_chart['daily_inconsistency'] = monthly_chart['old_daily'] - monthly_chart['daily_spent_diff'] / \
                                           monthly_chart['days_after']
    monthly_chart['old_daily'] = monthly_chart['old_daily'].fillna(method='bfill')
    monthly_chart['daily_inconsistency'] = monthly_chart['daily_inconsistency'].fillna(method='bfill')
    monthly_chart['fact_daily'] = monthly_chart['old_daily'] - monthly_chart['daily_inconsistency']
    monthly_chart['recommended_daily'] = monthly_chart['old_daily']

    spent_chart = monthly_chart[['date', 'avg_daily', 'fact_daily', 'recommended_daily']].dropna()
    spent_chart[['avg_daily', 'fact_daily', 'recommended_daily']] = spent_chart[['avg_daily', 'fact_daily',
                                                                                 'recommended_daily']] * -1

    x = spent_chart['date']
    y1 = -spent_chart['fact_daily']
    y2 = -spent_chart['recommended_daily']
    y3 = -spent_chart['avg_daily']
    fig, ax = plt.subplots()
    ax.set_title('Daily Spent')
    ax.plot(x, y1, '-')
    ax.plot(x, y2, '1--', color='red')
    ax.plot(x, y3, '--', color='black')
    ax.fill_between(x, y1, y2, where=(y1 > y2), color='red', alpha=0.3,
                    interpolate=True)
    ax.fill_between(x, y1, y2, where=(y1 <= y2), color='green', alpha=0.3,
                    interpolate=True)
    fig.tight_layout()
    plt.savefig('spent.png')

    fig, ax = plt.subplots()
    sns.lineplot(data=monthly_chart, x='date', y='planned')
    sns.lineplot(data=monthly_chart, x='date', y='balance')

    plt.savefig('status.png')

    latest_info = monthly_chart.dropna(subset=["planned_diff"]).iloc[-1]
    diff = latest_info["planned_diff"]
    diff_date = latest_info["date"].strftime("%d.%m")
    new_daily = latest_info['new_daily']

    context.bot.send_message(chat_id=update.effective_chat.id, text=f"*Budget status on {diff_date}*",
                             parse_mode=ParseMode.MARKDOWN)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open('status.png', 'rb'))
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open('spent.png', 'rb'))
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"Balance: *{diff:+.2f}₽*",
                             parse_mode=ParseMode.MARKDOWN)
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"Recommended daily budget: *{new_daily:.0f}₽*",
                             parse_mode=ParseMode.MARKDOWN)
    context.bot.send_message(chat_id=update.effective_chat.id, text='Have a lovely day ❤️')


def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(~in_known_filters, unknown))
    dp.add_handler(MessageHandler(recalculate_filter, recalculate_balance))
    dp.add_handler(MessageHandler(newlink_filter, generate_link))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

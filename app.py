import gc
import json
import os
from traceback import format_exc
import time


from flask import Flask, request  # pip install flask
import requests  # pip install requests
from werkzeug.datastructures import ImmutableOrderedMultiDict  # pip install flask


app = Flask(__name__)


@app.route('/')
def index():
    return 'Index for the JellyCraft PayPal IPN backend. If you are seeing this, it is active.'


def payment_hook(user_name, item_code, total_friendly, verified):
    payment_obj = {"user_name": user_name, "item_code": item_code, "total_friendly": total_friendly,
                   "verified": verified}
    message = json.dumps(payment_obj)
    discord_hook(message)


def discord_hook(message):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook_data = {
        "content": message,
        "username": "PayPal IPN Backend"
    }
    result = requests.post(webhook_url, json=webhook_data)
    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
    else:
        print(f"[Hook Run] {message}")


@app.route('/ipn/', methods=['POST'])
def ipn():
    values = "ERROR"
    try:
        arg = ''
        request.parameter_storage_class = ImmutableOrderedMultiDict
        values = request.form
        for x, y in values.items():
            arg += "&{x}={y}".format(x=x, y=y)
            print(x, y)

        # validate_url = 'https://ipnpb.sandbox.paypal.com' \
        validate_url = 'https://ipnpb.paypal.com' \
                       '/cgi-bin/webscr?cmd=_notify-validate{arg}' \
            .format(arg=arg)
        r = requests.get(validate_url)
        if r.text != 'VERIFIED':
            for i in range(3):  # Retry 3 times with 5s timeout
                time.sleep(5)
                r = requests.get(validate_url)
                if r.text == 'VERIFIED':
                    break
        if r.text == 'VERIFIED':
            print("VERIFIED!")
            try:
                user_name = request.form.get('option_selection1')
                item_code = request.form.get('item_number')

                payment_gross = request.form.get('mc_gross')
                if payment_gross is None:
                    payment_gross = 0

                payment_fee = request.form.get('mc_fee')
                if payment_fee is None:
                    payment_fee = 0
                total = max(payment_gross, payment_fee)
                currency = request.form.get('mc_currency')
                if currency is None:
                    currency = "USD"
                total_friendly = f"${total} {currency}"
                payment_hook(user_name, item_code, total_friendly, True)
                print(user_name, item_code, total_friendly)
            except Exception:
                print(format_exc())
            gc.collect()
            return r.text
        else:
            print("NOT VERIFIED!")
            raise

    except Exception as e:
        try:
            user_name = request.form.get('option_selection1')
            item_code = request.form.get('item_number')
            total = request.form.get('mc_fee')
            if total is None:
                total = 0
            currency = request.form.get('mc_currency')
            if currency is None:
                currency = "USD"
            total_friendly = f"${total} {currency}"
            payment_hook(user_name, item_code, total_friendly, False)
            print(user_name, item_code, total_friendly)
        except Exception:
            print(format_exc())
            print(values)
            discord_hook(values)
        return str(e)

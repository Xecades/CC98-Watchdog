# code adapted from https://github.com/ZJU-Turing/TuringDingBot/blob/master/src/utils/dingtalk.py

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv
from loguru import logger as L

load_dotenv()

DINGTALK_SEND_URL = os.getenv("DINGTALK_SEND_URL")
DINGTALK_SIGNATURE = os.getenv("DINGTALK_SIGNATURE")


def send_dingtalk_message(message: str):
    if not DINGTALK_SEND_URL or not DINGTALK_SIGNATURE:
        L.error("Dingtalk credentials not found in .env")
        return

    timestamp, sign = get_timestamp_and_sign()
    url = DINGTALK_SEND_URL + f"&timestamp={timestamp}&sign={sign}"
    data_raw = {"msgtype": "text", "text": {"content": message}}
    data = json.dumps(data_raw, ensure_ascii=False).encode("utf-8")
    res = requests.post(url, data=data, headers={"Content-Type": "application/json;charset=utf-8"})
    if res.status_code != 200:
        L.error("Failed to send dingtalk message")
    elif res.json()["errcode"] != 0:
        L.error(f"error message: {res.json()['errmsg']}")
    L.info(f"Dingtalk message sent successfully: {message}")


def get_timestamp_and_sign() -> tuple[str, str]:
    timestamp = str(round(time.time() * 1000))
    secret = str(DINGTALK_SIGNATURE).encode("utf-8")
    bytes_to_sign = f"{timestamp}\n{DINGTALK_SIGNATURE}".encode()
    hmac_code = hmac.new(secret, bytes_to_sign, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


if __name__ == "__main__":
    send_dingtalk_message("Hello, this is a test message from the script!")

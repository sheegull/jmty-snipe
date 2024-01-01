import json
import os
import time
from urllib.parse import quote
from urllib.request import urlopen

import gspread
import pandas as pd
import requests
import schedule
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()


def fetch_data(url):
    """指定されたURLからデータを取得し、解析する"""
    response = urlopen(url)
    return BeautifulSoup(response, "html.parser")


def scrape_items(bs):
    """商品情報をスクレイピングする"""
    items = []
    item_box = bs.findAll("li", {"class": "p-articles-list-item"})
    for item in item_box:
        title = item.find("div", {"class": "p-item-title"}).get_text().strip()
        price = item.find("div", {"class": "p-item-most-important"}).get_text().strip()
        favorite_element = item.find("span", {"class": "u-size-s js_fav_user_count"})
        favorite = favorite_element.get_text().strip() if favorite_element else "0"
        product_url = item.find("div", {"class": "p-item-title"}).find("a").get("href")
        items.append(
            {"タイトル": title, "価格": price, "お気に入り数": favorite, "商品URL": product_url}
        )
    return items


def load_previous_data(filename):
    """以前のデータをファイルから読み込む"""
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return {}


def update_spreadsheet(worksheet, new_items, previous_items):
    """スプレッドシートを更新する"""
    new_data_df = pd.DataFrame(new_items)
    existing_data = get_as_dataframe(worksheet)
    if existing_data is None or existing_data.empty:
        existing_data = pd.DataFrame(columns=["タイトル", "価格", "お気に入り数", "商品URL"])
    else:
        existing_data = existing_data.dropna(how="all", axis="columns")
    updated_data = pd.concat([new_data_df, existing_data], ignore_index=True)
    updated_data = updated_data[["タイトル", "価格", "お気に入り数", "商品URL"]]
    set_with_dataframe(worksheet, updated_data, resize=True, include_index=True)
    return updated_data


def send_line_notify(keyword, new_items, token):
    """LINEに通知を送る"""
    if new_items:
        latest_item = new_items[0]
        message = f"\n{keyword}新着情報: {latest_item['タイトル']}\n価格: {latest_item['価格']}\nURL: {latest_item['商品URL']}\n一覧: https://x.gd/9UIAz"
        requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": "Bearer " + token},
            params={"message": message},
        )


"""条件設定例

地域を指定：
all, tokyo, kanagawa, saitama, chiba, ibaraki, tochigi, gunma

カテゴリーを指定：
家具 = fur, 家電 = ele, 自転車 = bic

ジャンルを指定：
寝具 = 1227, ベッド = 1236, 椅子 = 1245, テーブル = 1255,
掃除機 = 1086, 洗濯機 = 1087, 冷蔵庫 = 1103, 電子レンジ = 1104, 炊飯器 = 1107,

価格範囲を指定：
最低価格 = min, 最高価格 = max

キーワードを指定（２つ以上の場合は+でつなぐ）：
panasonic+toshiba
"""


def job():
    previous_data = load_previous_data("previous_data.json")

    """スクレイピング設定"""
    location = "all"
    category = "fur"
    genre = "1255"
    min = "0"
    max = "10000"
    keyword = "テーブル"

    encoded_keyword = quote(keyword)
    url = f"https://jmty.jp/{location}/sale-{category}/g-{genre}?min={min}&max={max}&keyword={encoded_keyword}"
    bs = fetch_data(url)
    new_items = [
        item for item in scrape_items(bs) if item["商品URL"] not in previous_data
    ]

    if new_items:
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                "/Users/shee/dev/secret/spreadsheet-test-409604-7d92c4af7ade.json",
                [
                    "https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
            gc = gspread.authorize(credentials)
            worksheet = gc.open_by_key(os.environ.get("SPREADSHEET_KEY")).sheet1
            update_spreadsheet(worksheet, new_items, previous_data)
            send_line_notify(keyword, new_items, os.environ.get("LINE_TOKEN"))
        except Exception as e:
            print(f"エラー発生: {e}")

        with open("previous_data.json", "w") as file:
            json.dump(
                {item["商品URL"]: item for item in new_items}, file, ensure_ascii=False
            )


schedule.every(1).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)

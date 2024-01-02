import json
import os
import time
from datetime import datetime
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
        location_element = item.find("div", {"class": "p-item-secondary-important"})
        location = location_element.get_text().strip() if location_element else "不明"
        date_element = item.find("div", {"class": "u-color-gray"})
        date_text = date_element.get_text().strip() if date_element else "不明"
        date = date_text.replace("作成", "").strip()  # "作成"という単語を取り除く
        favorite_element = item.find("span", {"class": "u-size-s js_fav_user_count"})
        favorite = favorite_element.get_text().strip() if favorite_element else "0"
        product_url = item.find("div", {"class": "p-item-title"}).find("a").get("href")
        items.append(
            {
                "タイトル": title,
                "価格": price,
                "出品日": date,
                "取引場所": location,
                "お気に入り数": favorite,
                "商品URL": product_url,
            }
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
        existing_data = pd.DataFrame(
            columns=["タイトル", "価格", "出品日", "取引場所", "お気に入り数", "商品URL"]
        )
    else:
        existing_data = existing_data.dropna(how="all", axis="columns")
    updated_data = pd.concat([new_data_df, existing_data], ignore_index=True)
    updated_data = updated_data[["タイトル", "価格", "出品日", "取引場所", "お気に入り数", "商品URL"]]
    set_with_dataframe(worksheet, updated_data, resize=True, include_index=True)
    return updated_data


def send_line_notify(keyword, new_items, token):
    """LINEに通知を送る"""
    current_year = datetime.now().year  # 現在の年を取得
    for item in new_items:
        message = f"\n{keyword}の新着情報:\n{item['タイトル']}\n価格: {item['価格']}\n出品日: {current_year}年{item['出品日']}\n取引場所: {item['取引場所']}\nURL: {item['商品URL']}\n一覧: https://x.gd/9UIAz"
        requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": "Bearer " + token},
            params={"message": message},
        )
        time.sleep(1)  # LINEのAPI制限に引っかからないように1秒間隔をあける


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
    keyword = "flexispot"

    encoded_keyword = quote(keyword)
    url = f"https://jmty.jp/{location}/sale-{category}/g-{genre}?min={min}&max={max}&keyword={encoded_keyword}"
    bs = fetch_data(url)
    scraped_items = scrape_items(bs)

    # previous_dataにない商品のみを新しい商品として扱う
    new_items = [item for item in scraped_items if item["商品URL"] not in previous_data]

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
            # LINE Notifyに新しい商品の情報を送る
            send_line_notify(keyword, new_items, os.environ.get("LINE_TOKEN"))
            # previous_dataを更新し、新しい商品の情報を含める
            for item in new_items:
                previous_data[item["商品URL"]] = item
        except Exception as e:
            print(f"エラー発生: {e}")

        # 更新されたprevious_dataをファイルに保存
        with open("previous_data.json", "w") as file:
            json.dump(previous_data, file, ensure_ascii=False)


schedule.every(1).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)

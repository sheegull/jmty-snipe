import json
import os
import time
from datetime import datetime
from urllib.parse import quote
from urllib.request import urlopen

import requests
from bs4 import BeautifulSoup
from google.cloud import storage

# Cloud Storageのクライアントを初期化
storage_client = storage.Client()


def fetch_data(url):
    """指定されたURLからデータを取得し、解析する"""
    try:
        response = urlopen(url)
        return BeautifulSoup(response, "html.parser")
    except Exception as e:
        print(f"データの取得中にエラーが発生しました: {e}")
        return None


def scrape_items(bs):
    """商品情報をスクレイピングする"""
    if bs is None:
        return []
    items = []
    try:
        item_box = bs.select("li.p-articles-list-item", limit=10) # 制限を設ける
        for item in item_box:
            title = item.select_one(".p-item-title").get_text(strip=True)
            price = item.select_one(".p-item-most-important").get_text(strip=True)
            location = item.select_one(".p-item-secondary-important").get_text(strip=True)
            date_text = item.select_one(".u-color-gray").get_text(strip=True)
            date = date_text.replace("作成", "").strip()  # "作成"という単語を取り除く
            product_url = item.select_one(".p-item-title a").get("href")
            items.append(
                {
                    "タイトル": title,
                    "価格": price,
                    "出品日": date,
                    "取引場所": location,
                    "商品URL": product_url,
                }
            )
        return items
    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        return []


def load_previous_data(bucket_name, filename):
    """Cloud Storageから以前のデータを読み込む"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        if blob.exists():
            return json.loads(blob.download_as_string())
        return {}
    except Exception as e:
        print(f"データの読み込み中にエラーが発生しました: {e}")
        return {}


def save_previous_data(bucket_name, filename, data):
    """Cloud Storageにデータを保存する"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print(f"データの保存中にエラーが発生しました: {e}")


def send_line_notify(keyword, new_items, token):
    """LINEに通知を送る"""
    current_year = datetime.now().year  # 現在の年を取得
    for item in new_items:
        message = f"\n{keyword}の新着情報:\n{item['タイトル']}\n価格: {item['価格']}\n出品日: {current_year}年{item['出品日']}\n場所: {item['取引場所']}\nURL: {item['商品URL']}"
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


def job(event, context):
    bucket_name = os.environ.get("BUCKET_NAME")  # 環境変数からバケット名を取得
    if not bucket_name:
        print("バケット名が環境変数に設定されていません")
        return

    previous_data = load_previous_data(bucket_name, "previous_data1.json")
    if previous_data is None:
        print(f"前回のデータの読み込みに失敗しました")
        return

    """スクレイピング設定"""
    location = "all"
    category = "fur"
    genre = "1255"
    min = "0"
    max = "15000"
    keyword = "flexispot"

    encoded_keyword = quote(keyword)
    # カテゴリー用
    url = f"https://jmty.jp/{location}/sale-{category}?min={min}&max={max}&keyword={encoded_keyword}"
    # ジャンル用
    # url = f"https://jmty.jp/{location}/sale-{category}/g-{genre}?min={min}&max={max}&keyword={encoded_keyword}"
    bs = fetch_data(url)
    scraped_items = scrape_items(bs)

    if not scraped_items:
        print("スクレイピングに失敗しました")
        return

    for item in scraped_items:
        # previous_dataにない商品のみを新しい商品として扱う
        if item["商品URL"] not in previous_data:
            # LINE Notifyに新しい商品の情報を送る
            send_line_notify(keyword, [item], os.environ.get("LINE_TOKEN"))
            # previous_dataを更新し、新しい商品の情報を含める
            previous_data[item["商品URL"]] = item
            # 更新されたprevious_dataをCloud Storageに保存
            save_previous_data(bucket_name, "previous_data1.json", previous_data)

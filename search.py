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


def job():
    # 以前のデータを保存するファイル
    previous_data_file = "previous_data.json"

    # 以前のデータを読み込む
    if os.path.exists(previous_data_file):
        with open(previous_data_file, "r") as file:
            previous_data = json.load(file)
    else:
        previous_data = {}

    # 条件設定例 #############################################
    """
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
    ##########################################################

    # スクレイピング設定
    location = "all"
    category = "fur"
    genre = "1255"
    min = "0"
    max = "10000"
    keyword = "テーブル"

    encoded_keyword = quote(keyword)
    url = f"https://jmty.jp/{location}/sale-{category}/g-{genre}?min={min}&max={max}&keyword={encoded_keyword}"

    html = urlopen(url)
    bs = BeautifulSoup(html, "html.parser")
    item_box = bs.findAll("li", {"class": "p-articles-list-item"})

    new_items = []

    # 対象URLのスクレイピング
    for item in item_box:
        # 概要データ取得
        title = item.find("div", {"class": "p-item-title"}).get_text().strip()
        price = item.find("div", {"class": "p-item-most-important"}).get_text().strip()
        favorite_element = item.find("span", {"class": "u-size-s js_fav_user_count"})
        if favorite_element:
            favorite = favorite_element.get_text().strip()
        else:
            favorite = "0"
        product_url = item.find("div", {"class": "p-item-title"}).find("a").get("href")

        # 新しい商品のみを処理
        if product_url not in previous_data:
            new_item = {
                "タイトル": title,
                "価格": price,
                "お気に入り数": favorite,
                "商品URL": product_url,
            }
            new_items.append(new_item)
            previous_data[product_url] = new_item

    # 新しい商品がある場合のみ処理
    if new_items:
        # Googleスプレッドシートの設定
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                "/Users/shee/dev/secret/spreadsheet-test-409604-7d92c4af7ade.json",
                scope,
            )
            gc = gspread.authorize(credentials)
            secret_key = os.environ.get("SPREADSHEET_KEY")
            worksheet = gc.open_by_key(secret_key).sheet1

            # 新しいデータをDataFrameに変換
            new_data_df = pd.DataFrame(new_items)

            # 既存のスプレッドシートデータの読み込み
            existing_data = get_as_dataframe(worksheet)  # 最初の行を列名として使用
            existing_data = existing_data.dropna(how="all")  # 完全に空の行を削除
            existing_data = existing_data[["タイトル", "価格", "お気に入り数", "商品URL"]]  # 必要な列のみ保持

            # 新しいデータを既存のデータの上に追加
            updated_data = pd.concat([new_data_df, existing_data], ignore_index=True)

            # スプレッドシートの更新
            set_with_dataframe(worksheet, updated_data, resize=True, include_index=True)
        except gspread.SpreadsheetNotFound:
            print("スプレッドシートが見つかりません。IDを確認してください。")
        except Exception as e:
            print(f"スプレッドシートへのアクセスでエラーが発生しました: {e}")

        # LINE Notifyの設定とメッセージの送信
        try:
            latest_item = new_items[0]  # 新しい商品リストの最初の要素
            url = "https://notify-api.line.me/api/notify"  # 正しいAPIエンドポイント
            access_token = os.environ.get("LINE_TOKEN")
            headers = {"Authorization": "Bearer " + access_token}
            message = f"\n {keyword}の新着情報です。\n {latest_item['タイトル']}\n {latest_item['価格']}\n {latest_item['商品URL']}\n 一覧はこちら \n https://x.gd/9UIAz"
            params = {"message": message}
            r = requests.post(url, headers=headers, params=params)
        except Exception as e:
            print(f"LINE Notifyのエラー: {e}")

    # 新しいデータを保存
    with open(previous_data_file, "w") as file:
        json.dump(previous_data, file)


# スケジューリング
schedule.every(1).minutes.do(job)


while True:
    schedule.run_pending()
    time.sleep(1)

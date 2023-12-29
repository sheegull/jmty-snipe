import json
import time
from urllib.request import urlopen

import gspread
import pandas as pd
import requests
import schedule
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
import os

from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials


def job():
  location = "tokyo"
  df_main = pd.DataFrame(columns=["タイトル", "価格", "お気に入り数", "URL"])
  url = "https://jmty.jp/" + location + "/sale?max=0&min=0"
  html = urlopen(url)
  bs = BeautifulSoup(html, "html.parser")
  # last_page = bs.findAll("li", {"class": "last"}).get_text()
  item_box = bs.findAll("li", {"class": "p-articles-list-item"})
  item_box_count = len(item_box)

  # 対象URLのスクレイピング
  for i in range(item_box_count):

    # 概要データ取得
    title = item_box[i].find("div", {"class": "p-item-title"}).get_text()
    price = item_box[i].find("div", {"class": "p-item-most-important"}).get_text()
    favorite = item_box[i].find("span", {"class": "u-size-s js_fav_user_count"}).get_text()

    # 詳細データ取得
    for j in item_box[i].find("div", {"class": "p-item-title"}).select("a"):
      product_url = j.get("href")
      html_detail = urlopen(product_url)
      bs_detail = BeautifulSoup(html_detail, "html.parser")
      text = bs_detail.find("p", {"class": "sc-wraf99-0 bhfKek"}).get_text()
      data = pd.Series([title, price, favorite, product_url], index=df_main.columns)
      df_main = pd.concat([df_main, pd.DataFrame([data])], ignore_index=True)

  # Googleスプレッドシートの設定とデータの書き込み
    try:
      scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
      credentials = ServiceAccountCredentials.from_json_keyfile_name("/Users/shee/dev/secret/spreadsheet-test-409604-7d92c4af7ade.json", scope)
      gc = gspread.authorize(credentials)
      secret_key = os.environ.get("SPREADSHEET_KEY")
      worksheet = gc.open_by_key(secret_key).sheet1
      set_with_dataframe(worksheet, df_main, resize=True, include_index=True)
    except gspread.SpreadsheetNotFound:
      print("スプレッドシートが見つかりません。IDを確認してください。")
    except Exception as e:
      print(f"スプレッドシートへのアクセスでエラーが発生しました: {e}")

    # LINE Notifyの設定とメッセージの送信
    try:
        url = "https://notify-api.line.me/api/notify"  # 正しいAPIエンドポイント
        access_token = os.environ.get("LINE_TOKEN")
        headers = {'Authorization': 'Bearer ' + access_token}
        message = "本日のジモティーデータです。\n https://docs.google.com/spreadsheets/d/1Lz4BIkjpw5YWHkk-WFTzjD0xRRN9rrE7efN-HBWOSXw/edit?usp=sharing"
        params = {'message': message}
        r = requests.post(url, headers=headers, params=params)
    except Exception as e:
        print(f"LINE Notifyのエラー: {e}")

# スケジューリング
schedule.every(1).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)

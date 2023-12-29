from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup

# 対象地域を洗濯
location = "tokyo"
# スクレイピングのための初期準備
df_main = pd.DataFrame(columns=["タイトル", "価格", "お気に入り数", "内容", "商品URL"])
url = "https://jmty.jp/" + location + "/sale?max=0&min=0"

html = urlopen(url)
bs = BeautifulSoup(html, "html.parser")  # last_page = int(bs.find("li", {"class": last}).get_text())
item_box = bs.findAll("li", {"class": "p-articles-list-item"})
item_box_count = len(item_box)

# 対象URLのスクレピング
for i in range(item_box_count):
  # 概要データの取得
  title = item_box[i].find("div", {"class": "p-item-title"}).get_text()
  price = item_box[i].find("div", {"class": "p-item-most-important"}).get_text()
  favorite = item_box[i].find("span", {"class": "u-size-s js_fav_user_count"}).get_text()

  # 詳細データの取得
  for ii in item_box[i].find("div", {"class": "p-item-title"}).select("a"):
    product_url = ii.get("href")
    html_detail = urlopen(product_url)
    bs_detail = BeautifulSoup(html_detail, "html.parser")
    text = bs_detail.find("p", {"class": "sc-wraf99-0 bhfKek"}).get_text()
    new_data = pd.Series([title, price, favorite, text, product_url], index=df_main.columns)
    df_main = pd.concat([df_main, pd.DataFrame([new_data])], ignore_index=True)

  # CSVファイルの出力
  df_main.to_csv("jmty.csv", encoding="utf-8_sig")

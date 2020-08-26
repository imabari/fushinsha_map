import pathlib

import pandas as pd
import requests

import folium

GEO_URL = "https://raw.githubusercontent.com/geolonia/japanese-addresses/master/data/latest.csv"


def fetch_file(url, dir="."):

    r = requests.get(url)
    r.raise_for_status()

    p = pathlib.Path(dir, pathlib.PurePath(url).name)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open(mode="wb") as fw:
        fw.write(r.content)
    return p


if __name__ == "__main__":

    # 数字を漢数字
    kanji = str.maketrans("1234567890", "一二三四五六七八九〇")

    p_geo = fetch_file(GEO_URL, "src")

    df_geo = pd.read_csv(p_geo)

    # 愛媛県のみ抽出
    df_geo_ehime = df_geo[df_geo["都道府県名"] == "愛媛県"].copy()

    # 市名と町名を結合
    df_geo_ehime["address"] = df_geo_ehime["市区町村名"] + df_geo_ehime["大字町丁目名"]

    # 愛媛県警の不審者情報をスクレイピング
    df_tmp = (
        pd.read_html(
            "http://www.police.pref.ehime.jp/fushinsha.htm", match="概　要", header=0
        )[0]
        .fillna("")
        .astype(str)
    )

    # 内容を正規化
    df_tmp["概　要"] = df_tmp["概　要"].str.normalize("NFKC")

    # 項目ごとに分割
    df = df_tmp["概　要"].str.extract("(.+)◆.+:(.+)◆.+:(.+)◆.+:(.+)◆.+:(.+)")

    # 列名変更
    df.rename(columns={0: "管轄署", 1: "種別", 2: "日時", 3: "場所", 4: "状況"}, inplace=True)

    # 前後の空白文字を削除
    df = df.applymap(lambda s: s.strip())

    # かっこを削除
    df["管轄署"] = df["管轄署"].str.strip("()")

    # 住所間違い訂正
    df["場所"] = df["場所"].str.replace("常磐", "常盤")

    # 住所を漢数字に変換
    df["場所"] = df["場所"].apply(lambda s: s.translate(kanji))

    # 町名までに修正
    df["住所"] = df["場所"].str.replace(
        "(路上|施設|店舗|付近|一般住宅|住宅|アパート|マンション|公園|屋外|緑地|駐輪場|駐車場|河川敷|児童).*", "", regex=True
    )

    # 「甲乙丙の」を削除
    df["address"] = df["住所"].str.rstrip("甲乙丙の")

    # 北新田がないので新田に訂正
    df["address"] = df["address"].str.replace("西条市新田字北新田", "西条市新田")

    # 種別の確認
    df["種別"].unique()

    # アイコンの色を追加
    df["color"] = df["種別"].replace(
        {
            "のぞき・盗撮": "pink",
            "身体露出": "orange",
            "ちかん": "gray",
            "不審者": "purple",
            "声かけ": "green",
            "暴行": "red",
            "つきまとい": "blue",
            "写真撮影": "lightred",
            "建造物侵入": "darkred",
            "住居侵入": "darkred",
            "のぞき": "pink",
            "動画撮影": "lightred",
        }
    )

    # 上記に該当しない場合は黒
    df["color"] = df["color"].fillna("black")

    # 色の種類
    colors = {
        "lightred",
        "darkred",
        "darkblue",
        "pink",
        "gray",
        "green",
        "orange",
        "purple",
        "lightgray",
        "blue",
        "beige",
        "cadetblue",
        "darkgreen",
        "darkpurple",
        "lightblue",
        "black",
        "lightgreen",
        "red",
        "white",
    }

    # 住所から緯度経度をマージ
    df_ehime = df.merge(df_geo_ehime, how="left", on="address")

    p_csv = pathlib.Path("map", "ehime.csv")
    p_csv.parent.mkdir(parents=True, exist_ok=True)

    df_ehime.to_csv(p_csv, encoding="utf_8_sig")

    # 欠損を確認
    df_nan = df_ehime[df_ehime.isnull().any(axis=1)]
    p_nan = pathlib.Path("map", "nan.csv")
    df_nan.to_csv(p_nan, encoding="utf_8_sig")

    # 欠損を削除
    df_ehime.dropna(inplace=True)

    map = folium.Map(location=[34.06604300, 132.99765800], zoom_start=10)

    for i, r in df_ehime.iterrows():
        folium.Marker(
            location=[r["緯度"], r["経度"]],
            popup=folium.Popup(
                f'<p>{r["管轄署"]}</p><p>{r["種別"]}</p><p>{r["日時"]}</p><p>{r["場所"]}</p><p>{r["状況"]}</p>',
                max_width=300,
                min_width=150,
            ),
            icon=folium.Icon(color=r["color"]),
        ).add_to(map)

    p_map = pathlib.Path("map", "index.html")

    map.save(str(p_map))

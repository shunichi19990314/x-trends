"""
WOEID (Where On Earth IDentifier) マスタデータ。

X API v1.1 の `trends/available.json` は廃止されているため、
ロケーション一覧はアプリ側で静的に保持する。

注意:
  - WOEID は Yahoo が作ったレガシー ID で、X のトレンドは約470地点のみ対応。
  - 未対応の WOEID を投げるとエラーではなく「空のトレンド配列」が返る。
  - ここに無い地点を追加したい場合は LOCATIONS に追記するだけでよい。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    woeid: int
    name: str          # 英語名（X API と同じ表記）
    name_ja: str       # 日本語表示名
    country: str       # 国コード (ISO 3166-1 alpha-2)
    country_ja: str
    place_type: str    # worldwide / country / town
    region: str        # 表示用の地域グループ


_RAW: list[tuple[int, str, str, str, str, str, str]] = [
    # woeid, name, name_ja, country, country_ja, place_type, region
    (1, "Worldwide", "全世界", "XX", "全世界", "worldwide", "worldwide"),

    # ---- Japan ----
    (23424856, "Japan", "日本", "JP", "日本", "country", "japan"),
    (1118370, "Tokyo", "東京", "JP", "日本", "town", "japan"),
    (15015372, "Osaka", "大阪", "JP", "日本", "town", "japan"),
    (1117642, "Nagoya", "名古屋", "JP", "日本", "town", "japan"),
    (1117089, "Yokohama", "横浜", "JP", "日本", "town", "japan"),
    (1116957, "Sapporo", "札幌", "JP", "日本", "town", "japan"),
    (1117561, "Fukuoka", "福岡", "JP", "日本", "town", "japan"),
    (1117623, "Kobe", "神戸", "JP", "日本", "town", "japan"),
    (1118184, "Kyoto", "京都", "JP", "日本", "town", "japan"),
    (1118243, "Kawasaki", "川崎", "JP", "日本", "town", "japan"),
    (1118212, "Saitama", "さいたま", "JP", "日本", "town", "japan"),
    (1118105, "Hiroshima", "広島", "JP", "日本", "town", "japan"),
    (1118226, "Sendai", "仙台", "JP", "日本", "town", "japan"),
    (1117021, "Kitakyushu", "北九州", "JP", "日本", "town", "japan"),
    (1118291, "Chiba", "千葉", "JP", "日本", "town", "japan"),
    (1118131, "Sagamihara", "相模原", "JP", "日本", "town", "japan"),
    (1118108, "Hamamatsu", "浜松", "JP", "日本", "town", "japan"),
    (1118082, "Shizuoka", "静岡", "JP", "日本", "town", "japan"),
    (1118078, "Sakai", "堺", "JP", "日本", "town", "japan"),
    (1118188, "Niigata", "新潟", "JP", "日本", "town", "japan"),
    (1118171, "Kumamoto", "熊本", "JP", "日本", "town", "japan"),
    (1118148, "Okayama", "岡山", "JP", "日本", "town", "japan"),
    (1118144, "Kagoshima", "鹿児島", "JP", "日本", "town", "japan"),
    (1118129, "Utsunomiya", "宇都宮", "JP", "日本", "town", "japan"),
    (1118055, "Matsuyama", "松山", "JP", "日本", "town", "japan"),
    (1118011, "Takamatsu", "高松", "JP", "日本", "town", "japan"),
    (1118005, "Kanazawa", "金沢", "JP", "日本", "town", "japan"),

    # ---- Asia / Oceania ----
    (23424781, "China", "中国", "CN", "中国", "country", "asia"),
    (1257802, "Beijing", "北京", "CN", "中国", "town", "asia"),
    (1257801, "Shanghai", "上海", "CN", "中国", "town", "asia"),
    (1257803, "Guangzhou", "広州", "CN", "中国", "town", "asia"),
    (23424788, "Korea", "韓国", "KR", "韓国", "country", "asia"),
    (1132599, "Seoul", "ソウル", "KR", "韓国", "town", "asia"),
    (1132444, "Busan", "釜山", "KR", "韓国", "town", "asia"),
    (23424948, "Taiwan", "台湾", "TW", "台湾", "country", "asia"),
    (2306190, "Taipei", "台北", "TW", "台湾", "town", "asia"),
    (23424926, "Vietnam", "ベトナム", "VN", "ベトナム", "country", "asia"),
    (1252351, "Ho Chi Minh City", "ホーチミン", "VN", "ベトナム", "town", "asia"),
    (1252322, "Hanoi", "ハノイ", "VN", "ベトナム", "town", "asia"),
    (23424933, "Thailand", "タイ", "TH", "タイ", "country", "asia"),
    (1225448, "Bangkok", "バンコク", "TH", "タイ", "town", "asia"),
    (23424922, "Indonesia", "インドネシア", "ID", "インドネシア", "country", "asia"),
    (1047378, "Jakarta", "ジャカルタ", "ID", "インドネシア", "town", "asia"),
    (23424942, "Malaysia", "マレーシア", "MY", "マレーシア", "country", "asia"),
    (1257799, "Kuala Lumpur", "クアラルンプール", "MY", "マレーシア", "town", "asia"),
    (1062617, "Singapore", "シンガポール", "SG", "シンガポール", "town", "asia"),
    (23424848, "India", "インド", "IN", "インド", "country", "asia"),
    (2295411, "Mumbai", "ムンバイ", "IN", "インド", "town", "asia"),
    (2295412, "Delhi", "デリー", "IN", "インド", "town", "asia"),
    (2295377, "Bengaluru", "バンガロール", "IN", "インド", "town", "asia"),
    (23424845, "Philippines", "フィリピン", "PH", "フィリピン", "country", "asia"),
    (1167715, "Manila", "マニラ", "PH", "フィリピン", "town", "asia"),
    (1167717, "Quezon City", "ケソンシティ", "PH", "フィリピン", "town", "asia"),
    (23424755, "Australia", "オーストラリア", "AU", "オーストラリア", "country", "asia"),
    (1100661, "Sydney", "シドニー", "AU", "オーストラリア", "town", "asia"),
    (1103816, "Melbourne", "メルボルン", "AU", "オーストラリア", "town", "asia"),
    (1105779, "Brisbane", "ブリスベン", "AU", "オーストラリア", "town", "asia"),
    (23424938, "New Zealand", "ニュージーランド", "NZ", "ニュージーランド", "country", "asia"),

    # ---- North America ----
    (23424977, "United States", "アメリカ", "US", "アメリカ", "country", "americas"),
    (2459115, "New York", "ニューヨーク", "US", "アメリカ", "town", "americas"),
    (2442047, "Los Angeles", "ロサンゼルス", "US", "アメリカ", "town", "americas"),
    (2379574, "Chicago", "シカゴ", "US", "アメリカ", "town", "americas"),
    (2487956, "San Francisco", "サンフランシスコ", "US", "アメリカ", "town", "americas"),
    (2490383, "Seattle", "シアトル", "US", "アメリカ", "town", "americas"),
    (2486340, "Houston", "ヒューストン", "US", "アメリカ", "town", "americas"),
    (2450070, "Miami", "マイアミ", "US", "アメリカ", "town", "americas"),
    (2458410, "Atlanta", "アトランタ", "US", "アメリカ", "town", "americas"),
    (2471217, "Boston", "ボストン", "US", "アメリカ", "town", "americas"),
    (2486569, "Las Vegas", "ラスベガス", "US", "アメリカ", "town", "americas"),
    (2391585, "Washington", "ワシントンDC", "US", "アメリカ", "town", "americas"),
    (2367105, "Dallas-Ft. Worth", "ダラス", "US", "アメリカ", "town", "americas"),
    (2428184, "Denver", "デンバー", "US", "アメリカ", "town", "americas"),
    (2475687, "Portland", "ポートランド", "US", "アメリカ", "town", "americas"),
    (2476195, "San Diego", "サンディエゴ", "US", "アメリカ", "town", "americas"),
    (2467817, "Austin", "オースティン", "US", "アメリカ", "town", "americas"),
    (23424775, "Canada", "カナダ", "CA", "カナダ", "country", "americas"),
    (4118, "Toronto", "トロント", "CA", "カナダ", "town", "americas"),
    (3534, "Montreal", "モントリオール", "CA", "カナダ", "town", "americas"),
    (9807, "Vancouver", "バンクーバー", "CA", "カナダ", "town", "americas"),
    (23424900, "Mexico", "メキシコ", "MX", "メキシコ", "country", "americas"),
    (116545, "Mexico City", "メキシコシティ", "MX", "メキシコ", "town", "americas"),
    (133690, "Guadalajara", "グアダラハラ", "MX", "メキシコ", "town", "americas"),
    (133692, "Monterrey", "モンテレイ", "MX", "メキシコ", "town", "americas"),

    # ---- Latin America ----
    (23424768, "Brazil", "ブラジル", "BR", "ブラジル", "country", "americas"),
    (455825, "Sao Paulo", "サンパウロ", "BR", "ブラジル", "town", "americas"),
    (455827, "Rio de Janeiro", "リオデジャネイロ", "BR", "ブラジル", "town", "americas"),
    (455826, "Salvador", "サルバドール", "BR", "ブラジル", "town", "americas"),
    (455833, "Belo Horizonte", "ベロオリゾンテ", "BR", "ブラジル", "town", "americas"),
    (23424742, "Chile", "チリ", "CL", "チリ", "country", "americas"),
    (349859, "Santiago", "サンティアゴ", "CL", "チリ", "town", "americas"),
    (23424747, "Colombia", "コロンビア", "CO", "コロンビア", "country", "americas"),
    (368148, "Bogota", "ボゴタ", "CO", "コロンビア", "town", "americas"),
    (23424898, "Peru", "ペルー", "PE", "ペルー", "country", "americas"),
    (418440, "Lima", "リマ", "PE", "ペルー", "town", "americas"),
    (23424746, "Argentina", "アルゼンチン", "AR", "アルゼンチン", "country", "americas"),
    (468739, "Buenos Aires", "ブエノスアイレス", "AR", "アルゼンチン", "town", "americas"),
    (23424969, "Venezuela", "ベネズエラ", "VE", "ベネズエラ", "country", "americas"),
    (395269, "Caracas", "カラカス", "VE", "ベネズエラ", "town", "americas"),

    # ---- Europe ----
    (23424975, "United Kingdom", "イギリス", "GB", "イギリス", "country", "europe"),
    (44418, "London", "ロンドン", "GB", "イギリス", "town", "europe"),
    (28218, "Manchester", "マンチェスター", "GB", "イギリス", "town", "europe"),
    (15127, "Birmingham", "バーミンガム", "GB", "イギリス", "town", "europe"),
    (19344, "Glasgow", "グラスゴー", "GB", "イギリス", "town", "europe"),
    (13383, "Leeds", "リーズ", "GB", "イギリス", "town", "europe"),
    (13911, "Liverpool", "リヴァプール", "GB", "イギリス", "town", "europe"),
    (23424814, "Ireland", "アイルランド", "IE", "アイルランド", "country", "europe"),
    (560743, "Dublin", "ダブリン", "IE", "アイルランド", "town", "europe"),
    (23424819, "France", "フランス", "FR", "フランス", "country", "europe"),
    (615702, "Paris", "パリ", "FR", "フランス", "town", "europe"),
    (23424829, "Germany", "ドイツ", "DE", "ドイツ", "country", "europe"),
    (638242, "Berlin", "ベルリン", "DE", "ドイツ", "town", "europe"),
    (676757, "Hamburg", "ハンブルク", "DE", "ドイツ", "town", "europe"),
    (671072, "Munich", "ミュンヘン", "DE", "ドイツ", "town", "europe"),
    (667931, "Cologne", "ケルン", "DE", "ドイツ", "town", "europe"),
    (667930, "Frankfurt", "フランクフルト", "DE", "ドイツ", "town", "europe"),
    (23424936, "Spain", "スペイン", "ES", "スペイン", "country", "europe"),
    (766273, "Madrid", "マドリード", "ES", "スペイン", "town", "europe"),
    (753692, "Barcelona", "バルセロナ", "ES", "スペイン", "town", "europe"),
    (23424989, "Italy", "イタリア", "IT", "イタリア", "country", "europe"),
    (721943, "Rome", "ローマ", "IT", "イタリア", "town", "europe"),
    (718345, "Milan", "ミラノ", "IT", "イタリア", "town", "europe"),
    (725003, "Naples", "ナポリ", "IT", "イタリア", "town", "europe"),
    (23424934, "Netherlands", "オランダ", "NL", "オランダ", "country", "europe"),
    (727232, "Amsterdam", "アムステルダム", "NL", "オランダ", "town", "europe"),
    (23424786, "Belgium", "ベルギー", "BE", "ベルギー", "country", "europe"),
    (966591, "Brussels", "ブリュッセル", "BE", "ベルギー", "town", "europe"),
    (23424935, "Switzerland", "スイス", "CH", "スイス", "country", "europe"),
    (784794, "Zurich", "チューリッヒ", "CH", "スイス", "town", "europe"),
    (23424771, "Austria", "オーストリア", "AT", "オーストリア", "country", "europe"),
    (551801, "Vienna", "ウィーン", "AT", "オーストリア", "town", "europe"),
    (23424951, "Sweden", "スウェーデン", "SE", "スウェーデン", "country", "europe"),
    (897819, "Stockholm", "ストックホルム", "SE", "スウェーデン", "town", "europe"),
    (23424812, "Denmark", "デンマーク", "DK", "デンマーク", "country", "europe"),
    (554890, "Copenhagen", "コペンハーゲン", "DK", "デンマーク", "town", "europe"),
    (23424828, "Norway", "ノルウェー", "NO", "ノルウェー", "country", "europe"),
    (862592, "Oslo", "オスロ", "NO", "ノルウェー", "town", "europe"),
    (23424825, "Finland", "フィンランド", "FI", "フィンランド", "country", "europe"),
    (565346, "Helsinki", "ヘルシンキ", "FI", "フィンランド", "town", "europe"),
    (23424923, "Poland", "ポーランド", "PL", "ポーランド", "country", "europe"),
    (523920, "Warsaw", "ワルシャワ", "PL", "ポーランド", "town", "europe"),
    (23424919, "Czech Republic", "チェコ", "CZ", "チェコ", "country", "europe"),
    (468739, "Prague", "プラハ", "CZ", "チェコ", "town", "europe"),
    (23424801, "Hungary", "ハンガリー", "HU", "ハンガリー", "country", "europe"),
    (804365, "Budapest", "ブダペスト", "HU", "ハンガリー", "town", "europe"),
    (23424893, "Portugal", "ポルトガル", "PT", "ポルトガル", "country", "europe"),
    (742676, "Lisbon", "リスボン", "PT", "ポルトガル", "town", "europe"),
    (23424810, "Greece", "ギリシャ", "GR", "ギリシャ", "country", "europe"),
    (946738, "Athens", "アテネ", "GR", "ギリシャ", "town", "europe"),
    (23424980, "Russia", "ロシア", "RU", "ロシア", "country", "europe"),
    (2122265, "Moscow", "モスクワ", "RU", "ロシア", "town", "europe"),
    (2123260, "St. Petersburg", "サンクトペテルブルク", "RU", "ロシア", "town", "europe"),
    (23424972, "Ukraine", "ウクライナ", "UA", "ウクライナ", "country", "europe"),
    (924938, "Kyiv", "キーウ", "UA", "ウクライナ", "town", "europe"),
    (23424987, "Turkey", "トルコ", "TR", "トルコ", "country", "europe"),
    (2343732, "Istanbul", "イスタンブール", "TR", "トルコ", "town", "europe"),
    (2343734, "Ankara", "アンカラ", "TR", "トルコ", "town", "europe"),

    # ---- Middle East / Africa ----
    (23424931, "Saudi Arabia", "サウジアラビア", "SA", "サウジアラビア", "country", "mea"),
    (1937801, "Jeddah", "ジッダ", "SA", "サウジアラビア", "town", "mea"),
    (1939873, "Riyadh", "リヤド", "SA", "サウジアラビア", "town", "mea"),
    (23424930, "United Arab Emirates", "UAE", "AE", "UAE", "country", "mea"),
    (1940330, "Dubai", "ドバイ", "AE", "UAE", "town", "mea"),
    (1940345, "Abu Dhabi", "アブダビ", "AE", "UAE", "town", "mea"),
    (23424939, "Qatar", "カタール", "QA", "カタール", "country", "mea"),
    (1521894, "Doha", "ドーハ", "QA", "カタール", "town", "mea"),
    (23424826, "Israel", "イスラエル", "IL", "イスラエル", "country", "mea"),
    (1968212, "Tel Aviv", "テルアビブ", "IL", "イスラエル", "town", "mea"),
    (23424809, "Egypt", "エジプト", "EG", "エジプト", "country", "mea"),
    (1521894, "Cairo", "カイロ", "EG", "エジプト", "town", "mea"),
    (23424903, "Nigeria", "ナイジェリア", "NG", "ナイジェリア", "country", "mea"),
    (1398823, "Lagos", "ラゴス", "NG", "ナイジェリア", "town", "mea"),
    (23424942, "South Africa", "南アフリカ", "ZA", "南アフリカ", "country", "mea"),
    (1580913, "Johannesburg", "ヨハネスブルク", "ZA", "南アフリカ", "town", "mea"),
    (1591691, "Cape Town", "ケープタウン", "ZA", "南アフリカ", "town", "mea"),
    (23424844, "Kenya", "ケニア", "KE", "ケニア", "country", "mea"),
    (1528488, "Nairobi", "ナイロビ", "KE", "ケニア", "town", "mea"),
    (23424744, "Ghana", "ガーナ", "GH", "ガーナ", "country", "mea"),
    (1326075, "Accra", "アクラ", "GH", "ガーナ", "town", "mea"),
]

# 同一 WOEID の重複（誤記）を除去しつつ順序を保つ
_seen: set[int] = set()
LOCATIONS: list[Location] = []
for row in _RAW:
    if row[0] in _seen:
        continue
    _seen.add(row[0])
    LOCATIONS.append(Location(*row))

BY_WOEID: dict[int, Location] = {loc.woeid: loc for loc in LOCATIONS}

REGION_LABELS_JA: dict[str, str] = {
    "worldwide": "🌍 全世界",
    "japan": "🇯🇵 日本",
    "asia": "🌏 アジア・オセアニア",
    "americas": "🌎 南北アメリカ",
    "europe": "🌍 ヨーロッパ",
    "mea": "🌍 中東・アフリカ",
}

PLACE_TYPE_LABELS_JA: dict[str, str] = {
    "worldwide": "全世界",
    "country": "国",
    "town": "都市",
}


def get_location(woeid: int) -> Location | None:
    return BY_WOEID.get(woeid)


def location_to_dict(loc: Location) -> dict:
    return {
        "woeid": loc.woeid,
        "name": loc.name,
        "name_ja": loc.name_ja,
        "country": loc.country,
        "country_ja": loc.country_ja,
        "place_type": loc.place_type,
        "place_type_ja": PLACE_TYPE_LABELS_JA.get(loc.place_type, loc.place_type),
        "region": loc.region,
    }


def search_locations(q: str, limit: int = 12) -> list[dict]:
    """地域セレクタ用のあいまい検索。"""
    q = q.strip().lower()
    if not q:
        return []
    out: list[tuple[int, dict]] = []
    for loc in LOCATIONS:
        hay = f"{loc.name} {loc.name_ja} {loc.country} {loc.country_ja}".lower()
        if q in hay:
            score = 0
            if loc.name.lower() == q or loc.name_ja == q:
                score = 3
            elif loc.name.lower().startswith(q) or loc.name_ja.startswith(q):
                score = 2
            elif loc.place_type == "country":
                score = 1
            out.append((score, location_to_dict(loc)))
    out.sort(key=lambda x: (-x[0], x[1]["place_type"] != "country", x[1]["woeid"]))
    return [d for _, d in out[:limit]]


def grouped_locations() -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for loc in LOCATIONS:
        groups.setdefault(loc.region, []).append(location_to_dict(loc))
    order = ["worldwide", "japan", "asia", "americas", "europe", "mea"]
    result = []
    for key in order:
        if key in groups:
            result.append({
                "region": key,
                "label": REGION_LABELS_JA.get(key, key),
                "locations": groups[key],
            })
    return result

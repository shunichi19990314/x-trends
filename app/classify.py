"""
トレンド名の自動カテゴリ分類。

X API はカテゴリを返さないので、キーワード辞書 + ルールベースで推定する。
辞書は `KEYWORDS` に追加するだけで拡張できる（正規表現も可）。

精度は「だいたい合っていれば便利」レベルを想定。
機械学習で分類したい場合は classify() を差し替えるだけでよい。
"""

from __future__ import annotations

import re
from functools import lru_cache

CATEGORIES: dict[str, dict] = {
    "entertainment": {"ja": "エンタメ", "icon": "🎤", "color": "#f472b6"},
    "anime_game":    {"ja": "アニメ・ゲーム", "icon": "🎮", "color": "#a78bfa"},
    "sports":        {"ja": "スポーツ", "icon": "⚽", "color": "#34d399"},
    "news":          {"ja": "ニュース・政治", "icon": "📰", "color": "#f59e0b"},
    "tech":          {"ja": "テック", "icon": "💻", "color": "#38bdf8"},
    "finance":       {"ja": "経済・金融", "icon": "📈", "color": "#22c55e"},
    "lifestyle":     {"ja": "暮らし・グルメ", "icon": "🍜", "color": "#fb923c"},
    "hashtag":       {"ja": "ハッシュタグ", "icon": "#️⃣", "color": "#94a3b8"},
    "other":         {"ja": "その他", "icon": "✨", "color": "#64748b"},
}

# 優先度順。上のカテゴリほど強くマッチする。
KEYWORDS: dict[str, list[str]] = {
    "anime_game": [
        # アニメ・マンガ
        "鬼滅", "呪術", "ワンピース", "one piece", "ドラゴンボール", "ナルト", "naruto",
        "bleach", "ヒロアカ", "僕のヒーロー", "進撃の巨人", "エヴァ", "evangelion",
        "ガンダム", "gundam", "プリキュア", "precure", "ポケモン", "pokemon", "ピカチュウ",
        "ジブリ", "ghibli", "宮崎駿", "新海誠", "君の名は", "天気の子", "すずめの戸締まり",
        "チェンソーマン", "chainsaw man", "スパイファミリー", "spy×family", "spy family",
        "葬送のフリーレン", "フリーレン", "frieren", "推しの子", "oshibana",
        "ブルーロック", "bluelock", "ハイキュー", "haikyu", "ダンダダン", "dandadan",
        "薬屋のひとりごと", "ソロレベ", "俺だけレベルアップ", "マッシュル", "ウィッチウォッチ",
        "声優", "アニメ", "漫画", "コミックス", "単行本", "劇場版", "円盤", " Blu-ray",
        "anime", "manga", "mangax", "vtuber", "にじさんじ", "hololive", "ホロライブ",
        "初音ミク", "miku", "ボーカロイド", "vocaloid", "コスプレ", "cosplay",
        "コミケ", "comic market", "c10", "痛バ", "推し活", "聖地巡覧",
        # ゲーム
        "原神", "genshin", "崩壊スターレイル", "スターレイル", "starrail", "ゼンゼロ",
        "zzz", "鳴潮", "wuthering waves", "フォートナイト", "fortnite", "apex", "valorant",
        "ヴァロラント", "minecraft", "マイクラ", "スプラトゥーン", "splatoon", "スマブラ",
        "スマッシュブラザーズ", "マリオカート", "mario kart", "ゼルダ", "zelda",
        "どうぶつの森", "モンハン", "monster hunter", "ストリートファイター", "street fighter",
        "鉄拳", "tekken", "ウマ娘", "uma musume", "グラブル", "granblue", "fgo",
        "フェイトグランドオーダー", "プロセカ", "project sekai", "ブルアカ", "blue archive",
        "エペ", "nintendo switch", "switch2", "playstation", "ps5", "ps6", "xbox", "steam",
        "game awards", "steam deck", "エルデンリング", "elden ring", "デススト",
        "モンスターハンター", "パルワールド", "palworld", "ホグワーツ", "hogwarts",
        "ゲーム", "gamer", "esports", "eスポーツ", "実況", "配信者",
    ],
    "sports": [
        # サッカー
        "jリーグ", "j1", "j2", "浦和", "レッズ", "鹿島", "アントラーズ", "川崎フロンターレ",
        "フロンターレ", "マリノス", "ガンバ", "セレッソ", "ヴィッセル", "名古屋グランパス",
        "柏レイソル", "サンフレッチェ", "アルビレックス", "清水エスパルス", "コンサドーレ",
        "プレミアリーグ", "premier league", "ラ・リーガ", "laliga", "セリエa", "serie a",
        "ブンデス", "bundesliga", "リーグアン", "ligue 1", "ucl", "チャンピオンズリーグ",
        "champions league", "ヨーロッパリーグ", "europa league", "w杯", "ワールドカップ",
        "world cup", "日本代表", "サムライブルー", "なでしこ", "レアル", "real madrid",
        "バルサ", "barcelona", "バーサ", "マンシティ", "man city", "マンチェスター",
        "ユナイテッド", "arsenal", "アーセナル", "liverpool", "リバプール", "chelsea",
        "チェルシー", "tottenham", "トッテナム", "psg", "パリサンジェルマン", "bayern",
        "バイエルン", "inter milan", "インテル", "juventus", "ユベントス", "ac milan",
        "messi", "メッシ", "ronaldo", "ロナウド", "mbappe", "ムバッペ", "haaland",
        "ハーランド", "三笘", "mitoma", "久保建英", "kubo", "遠藤航", "鎌田", "kamada",
        "南野", "上田綺世", "堂安", "伊東純也", "冨安", "tomiyasu", "板倉", "守田",
        "サッカー", "soccer", "football", "ゴール", "hat-trick", "ハットトリック",
        # 野球
        "プロ野球", "npb", "ジャイアンツ", "読売", "タイガース", "阪神", "カープ", "広島東洋",
        "ドラゴンズ", "中日", "ベイスターズ", " DeNA", "スワローズ", "ヤクルト",
        "ファイターズ", "日本ハム", "イーグルス", "楽天", "マリーンズ", "ロッテ",
        "ライオンズ", "西武", "バファローズ", "オリックス", "ホークス", "ソフトバンク",
        "mlb", "大谷", "ohtani", "山本由伸", "yamamoto", "ダルビッシュ", "darvish",
        "鈴木誠也", "suzuki seiya", "今永", "imanaga", "松井裕樹", "千賀", "senga",
        "野球", "baseball", "ホームラン", "home run", "甲子園", "選抜", "ドラフト会議",
        "オールスター", "日本シリーズ", "wbc", "投手", "打者", "先発", "完封", "saヨナラ",
        # その他スポーツ
        "nba", "wnba", "レブロン", "lebron", "カリー", "curry", "八村", "hachimura",
        "渡邊雄太", "watanabe", "bリーグ", "バスケ", "バスケットボール", "basketball",
        "nfl", "super bowl", "スーパーボウル", "アメフト", "mls", "nhl", "スタンリーカップ",
        "テニス", "tennis", "全豪", "全仏", "全英", "ウィンブルドン", "wimbledon", "us open",
        "全米オープン", "ジョコビッチ", "djokovic", "アルカラス", "alcaraz", "シナー",
        "sinner", "大坂なおみ", "osaka naomi", "錦織", "nishikori",
        "ゴルフ", "golf", "マスターズ", "masters", "松山英樹", "笹生", "稲見",
        "f1", "フォーミュラ", "formula 1", "フェルスタッペン", "verstappen",
        "ハミルトン", "hamilton", "角田裕毅", "tsunoda", "ホンダ", "ルクレール",
        "bリーグ", "卓球", "table tennis", "張本", "harimoto", "早田", "伊藤美誠",
        "バドミントン", "badminton", "バレーボール", "volleyball", "石川祐希", "古賀",
        "フィギュア", "figure skating", "羽生結弦", "hanyu", "坂本花織", "浅田真央",
        "オリンピック", "olympic", "olympics", "パラリンピック", "paralympic",
        "マラソン", "marathon", "箱根駅伝", "駅伝", "陸上", "athletics", "水泳",
        "swimming", "瀬戸大也", "競泳", "柔道", "judo", "阿部詩", "レスリング",
        "wrestling", "ボクシング", "boxing", "井上尚弥", "naoya inoue", "モンスター",
        "ufc", "mma", "総合格闘技", "相撲", "sumo", "大相撲", "横綱", "力士", "番付",
        "skateboard", "スケートボード", "堀米雄斗", "horigome", "surfskate",
        "climbing", "クライミング", "eスポーツ", "cycling", "自転車", "ツール・ド・フランス",
        "tour de france", "rugby", "ラグビー", "w杯", "サッカー日本代表",
    ],
    "tech": [
        "openai", "chatgpt", "gpt-5", "gpt-6", "gpt5", "claude", "anthropic", "gemini",
        "grok", "xai", "xAI", "mistral", "llama", "meta ai", "deepseek", "qwen",
        "copilot", "midjourney", "stable diffusion", "sora", "ai", "人工知能", "生成ai",
        "llm", "agi", "機械学習", "machine learning", "neural", "gpu", "nvidia",
        "エヌビディア", "tsmc", "amd", "intel", "インテル", "apple", "アップル", "iphone",
        "ipad", "macbook", "ios", "android", "サムスン", "samsung", "galaxy",
        "google", "グーグル", "alphabet", "microsoft", "マイクロソフト", "windows",
        "amazon", "アマゾン", "aws", "azure", "meta", "メタ", "facebook", "instagram",
        "tiktok", "tik tok", "youtube", "ユーチューブ", "netflix", "ネトフリ",
        "tesla", "テスラ", "spacex", "イーロン", "elon musk", "musk", "マスク",
        "twitter", "ツイッター", "x社", "sns", "github", "linux", "python", "javascript",
        "typescript", "react", "vue", "next.js", "rust", "go言語", "java", "swift",
        "kotlin", "flutter", "unity", "unreal", "docker", "kubernetes", "api",
        "サイバー攻撃", "情報漏洩", "ランサムウェア", "セキュリティ", "バグ", "障害",
        "アップデート", "update", "release", "発表", "ローンチ", "launch",
        "startup", "スタートアップ", "ベンチャー", "資金調達", "量子コンピュータ",
        "quantum", "ev", "電気自動車", "自動運転", "self-driving", "robot", "ロボット",
        "pepper", "honda jet", "ドローン", "drone", "starlink", "スペースデブリ",
    ],
    "finance": [
        "日経平均", "日経", "nikkei", "株価", "株式", "株", "暴落", "暴騰", "急落", "急騰",
        "円安", "円高", "ドル円", "為替", "exchange rate", "yen", "dollar", "frb",
        "fed", "パウエル", "powell", "利上げ", "利下げ", "金利", "interest rate",
        "インフレ", "inflation", "デフレ", "消費者物価", "cpi", "gdp", "景気",
        "日銀", "boj", "植田", "ueda", "金融政策", "etf", "投資信託", "積立nisa",
        "nisa", "仮想通貨", "暗号資産", "crypto", "bitcoin", "ビットコイン", "btc",
        "ethereum", "イーサリアム", "eth", "solana", "xrp", "リップル", "dogecoin",
        "defi", "nft", "web3", "ステーブルコイン", "usdt", "トランプ関税", "関税",
        "tariff", "貿易摩擦", "決算", "earnings", "業績", "上場", "ipo", "倒産",
        "bankruptcy", "リストラ", "賃上げ", "春闘", "ボーナス", "給与", "賃金",
        "物価高", "ガソリン価格", "電気代", "ガス代", "住宅ローン", "ローン",
        "bank", "銀行", "みずほ", "三菱ufj", "三井住友", "証券", "野村", "大和",
        "goldman", "jp morgan", "ゴールドマン", "トヨタ株価", "ソニーg", "任天堂株",
    ],
    "news": [
        "地震", "earthquake", "津波", "tsunami", "台風", "typhoon", "豪雨", "大雨",
        "洪水", "flood", "土砂崩れ", "火山", "噴火", "eruption", "火災", "fire",
        "猛暑", "熱中症", "寒波", "大雪", "積雪", "暴風", "竜巻", "tornado",
        "hurricane", "ハリケーン", "台風接近", "警報", "注意報", "避難", "evacuation",
        "事件", "事故", "逮捕", "送検", "起訴", "判決", "裁判", "公判", "有罪", "無罪",
        "殺人", "強盗", "詐欺", "窃盗", "放火", "傷害", "警察", "検察", "容疑者",
        "crash", "derailment", "脱線", "衝突", "墜落", "crash", "事故死", "死亡",
        "被害", "負傷", "行方不明", "missing", "捜索",
        "選挙", "election", "投票", "vote", "当選", "落選", "衆議院", "参議院",
        "国会", "diet", "首相", "総理", "内閣", "cabinet", "党首", "総裁選",
        "代表選", "立候補", "政党", "自民党", "立憲", "維新", "公明", "共産",
        "れいわ", "国民民主", "参政党", "政権", "解散", "組閣", "大臣", "知事",
        "都知事", "市長", "議会", "法案", "法律", "改正", "閣議決定",
        "外交", "サミット", "首脳会談", "会談", "国連", "un", "nato", " nato",
        "ロシア", "russia", "ウクライナ", "ukraine", "侵攻", "invasion", "停戦",
        "ceasefire", "和平", "制裁", "sanction", "イスラエル", "israel", "ガザ",
        "gaza", "イラン", "iran", "北朝鮮", "north korea", "中国", "china", "米中",
        "trump", "トランプ", "大統領", "president", "ホワイトハウス", "政権交代",
        "罷免", "弾劾", "impeach", "抗議", "protest", "デモ", "demo", "暴動", "riot",
        "strike", "ストライキ", "政府", "government", "省庁", "厚労省", "文科省",
        "経産省", "防衛省", "外務省", "財務省", "総務省", "国交省", "環境省",
        "皇室", "天皇", "皇后", "皇族", "king", "queen", "royal family", "王室",
        "新型コロナ", "covid", "コロナ", "感染症", "ワクチン", "vaccine", "集団感染",
        "パンデミック", "malaria", "鳥インフル", "麻疹", "measles", "患者", "医療",
        "病院", "医師", "看護師", "救急", "熱中症搬送",
        "少子化", "人口減少", "移民", "immigration", "難民", "refugee", "visa",
        "ビザ", "入国", "出国", "パスポート",
    ],
    "lifestyle": [
        "コンビニ", "セブン", "ファミマ", "ローソン", "新商品", "コラボ", "限定",
        "キャンペーン", "発売", "売り切れ", "完売", "sold out", "セール", "sale",
        "ブラックフライデー", "福袋", "クーポン", "ポイント", "paypay", "楽天ペイ",
        "suica", "pasmo", "icカード",
        "ラーメン", "寿司", "すし", "焼肉", "焼鳥", "うどん", "そば", "カレー",
        "パンケーキ", "タピオカ", "スイーツ", "ケーキ", "チョコレート", "アイス",
        "スターバックス", "スタバ", "starbucks", "マクドナルド", "マック", "mcdonald",
        "吉野家", "すき家", "松屋", "ココス", "ガスト", "サイゼ", "サイゼリヤ",
        "ケンタ", "kfc", "サブウェイ", "ピザ", "pizza", "バーガー", "burger",
        "ミスド", "ドーナツ", "サーティワン", "ハーゲンダッツ", "カルディ", "成城石井",
        "業務スーパー", "コストコ", "costco", "ドンキ", "ユニクロ", "uniqlo", "gu",
        "しまむら", "無印", "無印良品", "muji", "ニトリ", "ikea", "イケア",
        "zara", "h&m", "shein", "ワークマン",
        "旅行", "travel", "観光", "trip", "airbnb", "ホテル", "hotel", "旅館",
        "温泉", "リゾート", "ディズニー", "disney", "usj", "ユニバ", "ジブリパーク",
        "サンリオ", "ピューロ", "theme park", "テーマパーク",
        "美容", "コスメ", "メイク", "スキンケア", "化粧", "美容室", "ヘア",
        "ダイエット", "diet", "筋トレ", "ワークアウト", "workout", "ヨガ", "yoga",
        "ランニング", "running", "健康", "健康診断", "睡眠", "sleep", "瞑想",
        "料理", "レシピ", "recipe", "お弁当", "弁当", "bento", "節約", "暮らし",
        "インテリア", "収納", "掃除", "洗濯", "育児", "子育て", "保育園",
        "幼稚園", "小学校", "中学校", "高校", "大学", "受験", "入学試験", "偏差値",
        "就活", "就職活動", "転職", "副業", "リモートワーク", "在宅勤務", "通勤",
        "満員電車", "交通", "jr", "新幹線", "shinkansen", "山手線", "地下鉄",
        "metro", "subway", "bus", "路線", "運休", "遅延", "終電",
        "犬", "猫", "ペット", "dog", "cat", "動物", "animal", "水族館", "動物園",
        "映画", "movie", "cinema", "ドラマ", "drama", "テレビ", "tv", "番組",
        "バラエティ", "nhk", "日テレ", "tbs", "テレ朝", "フジテレビ", "ネットフリックス",
        "音楽", "music", "ライブ", "live", "コンサート", "concert", "フェス",
        "festival", "夏フェス", "rock in japan", "フジロック", "サマソニ",
        "summer sonic", "cd", "アルバム", "新曲", "mv", "music video", "カラオケ",
        "karaoke", "spotify", "apple music",
        "天気", "weather", "気温", "湿度", "花粉", "pm2.5", "黄砂", "紫外線",
        "桜", "sakura", "花見", "紅葉", "紅葉狩り", "梅雨", "雪", "snow",
        "初雪", "夏日", "真夏日", "猛暑日", "熱帯夜", "冬日",
    ],
    "entertainment": [
        "芸能", "芸能人", "アイドル", "idol", "俳優", "女優", "actress", "actor",
        "タレント", "モデル", "model", "歌手", "singer", "アーティスト", "artist",
        "ミュージシャン", "musician", "バンド", "band", "グループ", "デビュー",
        "debut", "卒業", "脱退", "加入", "新メンバー", "活動休止", "引退",
        "retirement", "結婚", "婚約", "離婚", "破局", "熱愛", "交際", "妊娠",
        "出産", "第一子", "第二子", "誕生日", "生誕祭", "birthday",
        "スキャンダル", "不倫", "浮気", "謝罪", "文春", "週刊文春", "フライデー",
        "東スポ", "会見", "press conference", "炎上", "物議", "批判", "騒動",
        "裁判", "訴訟", "契約解除", "所属事務所", "事務所", "退所", "移籍",
        "arashi", "嵐", "smap", "tokio", "v6", "kinpuri", "kinpri", "キンプリ",
        "king & prince", "snow man", "snowman", "スノーマン", "sno", "なにわ男子",
        "naniwa danshi", "travis japan", "timelesz", "west.", "sexy zone",
        "hey! say! jump", "hey say jump", "kinki kids", "domoto", "堂本",
        "山下智久", "yamashita", "生田斗真", "松本潤", "matsumoto jun", "櫻井翔",
        "sakurai sho", "相葉雅紀", "aiba", "二宮和也", "ninomiya", "大野智",
        "ohno", "木村拓哉", "kimura takuya", "キムタク", "中居正広", "nakai",
        "稲垣吾郎", "inagaki", "草彅剛", "kusanagi", "香取慎吾", "katori",
        "福山雅治", "fukuyama", "星野源", "hoshino gen", "新垣結衣", "aragaki yui",
        "ガッキー", "綾瀬はるか", "ayase haruka", "石原さとみ", "ishihara satomi",
        "北川景子", "kitagawa keiko", "佐々木希", "sasaki nozomi", "橋本環奈",
        "hashimoto kanna", "かんな", "永野芽郁", "nagano mei", "広瀬すず",
        "hirose suzu", "広瀬アリス", "浜辺美波", "hamabe minami", "上白石萌音",
        "森七菜", "mori nana", "吉高由里子", "yoshitaka yuriko", "多部未華子",
        "tabe mikako", "戸田恵梨香", "toda erika", "満島ひかり", "mitsushima",
        "安藤サクラ", "ando sakura", "長澤まさみ", "nagasawa masami", "松たか子",
        "matsu takako", "天海祐希", "amami yuki", "米倉涼子", "yonekura",
        "菅田将暉", "suda masaki", "山崎賢人", "yamazaki kento", "横浜流星",
        "yokohama ryusei", "吉沢亮", "yoshizawa ryo", "松坂桃李", "matsuzaka",
        "小栗旬", "oguri shun", "妻夫木聡", "tsumabuki", "阿部寛", "abe hiroshi",
        "役所広司", "yakusho", "渡辺謙", "watanabe ken", "真田広之", "sanada",
        "浅野忠信", "asano tadanobu", "坂口健太郎", "sakaguchi kentaro",
        "中村倫也", "nakamura tomoya", "高橋一生", "takahashi issey",
        "竹内涼真", "takeuchi ryoma", "北村匠海", "kitamura takumi",
        "mrs. green apple", "ミセス", "ヨルシカ", "yorushika", "yoasobi",
        "ado", "vaundy", "official髭男dism", "ヒゲダン", "back number",
        "backnumber", "米津玄師", "yonezu kenshi", "レミオロメン", "aimyon",
        "あいみょん", "宇多田ヒカル", "utada hikaru", "hikaru utada", "椎名林檎",
        "sheena ringo", "スピッツ", "spitz", "ミスチル", "mr.children", "b'z",
        "glay", "l'arc", "ラルク", "x japan", "hide", "hyde", "yoshiki",
        "sakanaction", "サカナクション", "perfume", "babymetal", "ベビメタ",
        "one ok rock", "ワンオク", "radwimps", "ラッド", "king gnu", "キングヌー",
        "number_i", "ナンバーアイ", "imase", "imase", "緑黄色社会", "リョクシャカ",
        "super beaver", "sumika", "sumika", "マカロニえんぴつ", "macaroni",
        "yama", "優里", "yuuri", "tani yuuki", "谷口悠樹", "aimer", "aimer",
        "lisa", "リサ", "adieu", " milet", "milet", "sawano", "澤野弘之",
        # K-POP / グローバル
        "bts", "防弾少年団", "bangtan", "jungkook", "jimin", "v (bts)", "taehyung",
        "suga", "rm", "j-hope", "jhope", "jin", "blackpink", "ブラックピンク",
        "jennie", "jisoo", "rosé", "rose blackpink", "lisa blackpink", "lisa",
        "newjeans", "ニュージーンズ", "le sserafim", "ルセラフィム", "ive",
        "aespa", "エスパ", "twice", "トゥワイス", "stray kids", "スキズ",
        "enhypen", "エンハイプン", "txt", "seventeen", "セブチ", "atez", "nct",
        "exo", "red velvet", "itzy", "stayc", "illit", "kiss of life",
        "kpop", "k-pop", "mama", "melon", "gaon", "circle chart", "ビルボード",
        "billboard", "grammy", "グラミー", "mtv", "vma", "coachella",
        "taylor swift", "テイラー", "beyoncé", "beyonce", "ariana grande",
        "ariana", "ariana grande", "billie eilish", "billie", "olivia rodrigo",
        "sabrina carpenter", "sabrina", "dua lipa", "the weeknd", "drake",
        "kanye", "ye", "travis scott", "kendall jenner", "kylie jenner",
        "kim kardashian", "khloe", "hailey bieber", "justin bieber", "selena",
        "selena gomez", "zendaya", "tom holland", "timothée", "timothee chalamet",
        "leonardo dicaprio", "ディカプリオ", "brad pitt", "ブラッドピット",
        "tom cruise", "トムクルーズ", "spider-man", "スパイダーマン", "marvel",
        "マーベル", "avengers", "アベンジャーズ", "deadpool", "デッドプール",
        "batman", "バットマン", "superman", "スーパーマン", "dc", "joker",
        "ジョーカー", "harry potter", "ハリーポッター", "hogwarts legacy",
        "star wars", "スターウォーズ", "jedi", "ジェダイ", "mandalorian",
        "avatar", "アバター", "james cameron", "cameron", "spielberg",
        "スピルバーグ", "nolan", "ノーラン", "tarantino", "タランティーノ",
        "scorsese", "スコセッシ", "villeneuve", "ヴィルヌーヴ", "miyazaki",
        "宮崎", "スタジオジブリ", "pixar", "ピクサー", "disney+",
        "prime video", "アマプラ", "hulu", "u-next", "abema", "tver", "テレビ番組",
        "紅白", "紅白歌合戦", "nhk紅白", "music station", "ミュージックステーション",
        "mステ", "cdtv", "ベストヒット歌謡祭", "日テレ系", "24時間テレビ",
        "27時間テレビ", "笑ってはいけない", "gaki no tsukai", "ダウンタウン",
        "downtown", "浜田雅功", "松本人志", "matsumoto hitoshi", "明石家さんま",
        "sanma", "有吉弘行", "ariyoshi", "マツコデラックス", "matsuko",
        "ナインティナイン", "ナイナイ", "岡村隆史", "矢部浩之", "ロンドンブーツ",
        "ロンブー", "田村淳", "お笑い", "漫才", "manzai", "コント", "m-1",
        "m1グランプリ", "キングオブコント", "koc", "r-1", "r1グランプリ",
        "THE W", "the w", "女芸人", "吉本", "よしもと", "松竹芸能", "ワタナベ",
        "アミューズ", "スターダスト", "ジャニーズ", "johnnys", "smile-up",
        "starto", "starto entertainment", "STARTO", "timelesz project",
        "タイプロ", "プロデュース101", "produce 101", "オーディション",
        "audition", "nizi project", "niziu", "ニジュー", "nizi", "j.y. park",
        "jyp", "hybe", "ハイブ", "yg", "smエンタ", "sm entertainment",
        # 映画 / ドラマ
        "興行収入", "box office", "映画化", "実写化", "ドラマ化", "アニメ化",
        "主演", "助演", "監督", "脚本", "撮影", "クランクイン", "クランクアップ",
        "公開", "release", "premiere", "プレミア", "試写会", "舞台挨拶",
        "oscar", "オスカー", "academy award", "アカデミー賞", "ゴールデン",
        "golden globe", "ゴールデングローブ", "カンヌ", "cannes", "ベネチア",
        "venice", "ベルリン映画祭", "berlinale", "日本アカデミー賞",
        "エミー賞", "emmy", "tony award", "トニー賞",
        "ドラマ", "series", "season", "シーズン", "episode", "エピソード",
        "最終回", "finale", "第1話", "第2話", "視聴率", "ratings",
        "squid game", "イカゲーム", "wednesday", "ウェンズデー", "stranger things",
        "ストレンジャーシングス", "the last of us", "house of the dragon",
        "rings of power", "the crown", "bridgerton", "white lotus",
        "shogun", "ショーグン", "true detective", "severance", "the bear",
        "エミリー", "emily in paris", "la casa de papel", "ペーパーハウス",
        "ワンピース netflix", "one piece netflix", "アバター 伝説の少年アン",
    ],
}

_HASHTAG_RE = re.compile(r"^#[^#\s]*[A-Za-z\u3040-\u30ff\u4e00-\u9fff][^#\s]*$", re.I)
_JA_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _compile() -> list[tuple[str, re.Pattern]]:
    compiled: list[tuple[str, re.Pattern]] = []
    for category, words in KEYWORDS.items():
        for w in words:
            w = w.strip()
            if not w:
                continue
            # 英字のみの語は単語境界でマッチさせ、部分一致の誤爆を防ぐ
            if re.fullmatch(r"[A-Za-z0-9.\-+&'’! ]+", w):
                pattern = r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])"
            else:
                pattern = re.escape(w)
            compiled.append((category, re.compile(pattern, re.I)))
    return compiled


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[str, re.Pattern]]:
    return _compile()


def classify(name: str) -> str:
    """トレンド名からカテゴリIDを返す。"""
    text = (name or "").strip()
    if not text:
        return "other"

    # 「#〜」はユーザーが意図的に付けたタグなので最優先でハッシュタグ扱い
    if _HASHTAG_RE.match(text):
        return "hashtag"

    lowered = text.lower()
    scores: dict[str, int] = {}
    for category, pattern in _patterns():
        matches = pattern.findall(lowered)
        if matches:
            # 長い語ほど強いシグナル
            weight = max(len(m) for m in matches)
            scores[category] = scores.get(category, 0) + weight

    if scores:
        return max(scores.items(), key=lambda kv: kv[1])[0]

    return "other"


def category_meta(category_id: str) -> dict:
    meta = CATEGORIES.get(category_id, CATEGORIES["other"])
    return {"id": category_id, "ja": meta["ja"], "icon": meta["icon"], "color": meta["color"]}


def all_categories() -> list[dict]:
    return [category_meta(cid) for cid in CATEGORIES]

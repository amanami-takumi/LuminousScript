# LuminasScript - ビジュアルノベルゲーム生成ツール

CSVファイルから、ビジュアルノベル形式のウェブゲームを自動生成するPythonツールです。

## 📋 必要要件

- Python 3.6以上
- 標準ライブラリのみ使用（追加インストール不要）

## 🚀 使い方

### 1. ディレクトリ構成を準備

```
project/
├── luminas_script.py    # メインスクリプト
├── input/               # 入力ファイル
│   ├── scenario.csv     # シナリオCSVファイル
│   └── assets/          # 画像・音声ファイル
│       ├── backgrounds/ # 背景画像
│       └── characters/  # キャラクター立ち絵
└── output/              # 生成されたHTMLの出力先
```

### 2. CSVファイルを作成

`input/scenario.csv` にシナリオを記述します。

**CSVカラム:**
- `scene_id` - シーン識別子（必須）
- `person_name` - 発話者名
- `text` - セリフ・テキスト
- `background_image` - 背景画像ファイル名
- `center_standing_portrait_image` - 中央の立ち絵
- `left_standing_portrait_image` - 左の立ち絵
- `right_standing_portrait_image` - 右の立ち絵
- `effect` - エフェクト（将来実装）
- `sounds` - 効果音（将来実装）
- `bgm` - BGM（将来実装）

**scene_idの命名規則:**
- `1-T` - チャプター1のタイトル
- `1-1` - チャプター1のシーン1
- `1-Q` - チャプター1の選択肢
- `1-A-1` - チャプター1、ルートAのシーン1
- `1-B-1` - チャプター1、ルートBのシーン1
- `1-E` - チャプター1のエンディング

### 3. 画像を配置

画像ファイルを以下のディレクトリに配置:
- 背景: `input/assets/backgrounds/`
- キャラクター: `input/assets/characters/`

対応形式: PNG, JPG, JPEG, GIF, WebP

### 4. スクリプトを実行

```bash
python luminas_script.py
```

または、CSVファイル名を指定:

```bash
python luminas_script.py memo.csv
```

### 5. 生成されたゲームをプレイ

`output/game.html` をブラウザで開いてください！

## 🎮 ゲームの機能

### タイトル画面
- ニューゲーム
- ロード（localStorageから）
- 設定
- クレジット

### ゲーム中
- クリックでテキスト送り
- 選択肢による分岐
- 自動セーブ
- メニューからセーブ/ロード

### 設定
- テキスト速度調整
- BGM音量調整（将来実装）
- SE音量調整（将来実装）

## 📝 CSVの例

```csv
scene_id,person_name,text,background_image,center_standing_portrait_image,left_standing_portrait_image,right_standing_portrait_image
1-T,,第一章 タイトル,bg_1_morning_bed,,,
1-1,天波たくみ,"おはよう！
もー、今日もお寝坊さん？",bg_1_morning_bed,,,
1-2,Astrolabe,"別に寝てたっていいじゃん。
学校があるわけでも、仕事があるわけでもないんだしさ",bg_myroom_1,sp_astrolabe_jitome,,
1-Q,,"A 実は今日から学校に行くことになりました！
B それもそうだね",bg_myroom_1,,,
1-A-1,天波たくみ,"実は、伝えたいことがあって。
今日からね。あなたは。",bg_myroom_1,,,
1-A-2,Astrolabe,ごくり。。.,bg_myroom_1,,sp_amanamitakumi_smile,sp_astrolabe_jitome
1-A-3,天波たくみ,学校に行くことになりました！,bg_myroom_1,,sp_amanamitakumi_smile,
1-B-1,天波たくみ,"そりゃそうだ。
でもさ、学校とか行ってみない？",bg_myroom_1,,sp_amanamitakumi_nigawarai,
```

## 🎨 デザインの特徴

- モダンなグラデーション背景
- スムーズなトランジション効果
- レスポンシブデザイン
- ダークテーマのUI
- アニメーション付きボタン

## 📄 ライセンス

Apache 2.0

## 🔧 トラブルシューティング

### 画像が表示されない
- ファイル名が正確か確認
- 画像ファイルが正しいディレクトリにあるか確認
- 対応形式（PNG, JPG等）か確認

### セーブが機能しない
- ブラウザのlocalStorageが有効か確認
- プライベートブラウジングモードでは動作しません

### CSVが読み込めない
- UTF-8エンコーディングで保存されているか確認
- CSVの形式が正しいか確認（カラム名など）

## 🚀 将来の拡張予定

- [ ] BGM/SE再生機能
- [ ] 画面エフェクト（フェード、振動等）
- [ ] オートモード
- [ ] タイプライター効果
- [ ] バックログ機能
- [ ] スキップ機能

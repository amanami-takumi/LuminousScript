↓なんか勝手に書かれてました

# LuminasScript - ビジュアルノベルゲーム生成ツール

CSVファイルから、ビジュアルノベル形式のウェブゲームを自動生成するPythonツールです。
WebGUIを別途用意しており、そちらからより直感的で集団的な開発を可能とします。

## 設計思想

1. ブラウザで動作が完結すること
2. ローカルで動作できること
3. CSV及びConfigで制御されること（CLI動作が可能なこと）
4. 簡素かつ普遍であること

## 必要要件

### 開発側

- Python 3.6以上
- 標準ライブラリのみ使用（追加インストール不要）

### 利用側

- Chromeが動作する端末

## 使い方

### 1. ディレクトリ構成を準備

```
project/
├── luminas_script.py    # メインスクリプト
├── input/               # 入力ファイル
│   ├── scenario.csv     # シナリオCSVファイル
│   └── assets/          # 画像・音声ファイル
│       ├── backgrounds/ # 背景画像
│       ├── characters/  # キャラクター立ち絵
│       └── effect/      # 画面最前面のエフェクト画像
└── output/              # 生成されたHTMLの出力先
```

### 2. CSVファイルを作成

`input/file_name.csv` にシナリオを記述します。

**CSVカラム:**

- `scene_id` - シーン識別子（必須）
- `person_name` - 発話者名。`<$costom_name$>`でユーザ名を代入できる
- `text` - セリフ・テキスト
- `background_image` - 背景画像ファイル名
- `center_standing_portrait_image` - 中央の立ち絵
- `left_standing_portrait_image` - 左の立ち絵
- `right_standing_portrait_image` - 右の立ち絵
- `effect` - 最前面に重ねるエフェクト画像。`<file|M,S120,X10,Y-20,V2>` 記法対応
- `sounds` - 効果音（将来実装）
- `bgm` - BGM
- `scripts` - システム動作に介入できます
- `memo` - メモをかけます

**scene_idの命名規則:**

- `1-T` - チャプター1のタイトル
- `1-1` - チャプター1のシーン1
- `1-Q` - チャプター1の選択肢
- `1-A-1` - チャプター1、ルートAのシーン1
- `1-B-1` - チャプター1、ルートBのシーン1
- `1-M` - チャプター1、ルートAとBの収束ルート
- `1-E` - チャプター1のエンディング

### 3. 画像を配置

画像ファイルを以下のディレクトリに配置:

- 背景: `input/assets/backgrounds/`
- キャラクター: `input/assets/characters/`
- エフェクト: `input/assets/effect/`
- BGM: `input/assets/bgms/`

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

`output/game.html` をブラウザで開いてください。

## ゲームの機能

### タイトル画面

- ニューゲーム
- ロード（localStorage）
- 設定
- クレジット

### ゲーム中

- クリックでテキスト送り
- 選択肢による分岐
- 自動セーブ
- メニューからセーブ/ロード
- セーブは最大99枠に対応します
- セーブはインポートとエクスポートに対応します

### 設定

- テキスト速度調整
- BGM音量調整
- 名前の設定機能

## CSVの例

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

## カスタム記法について

テキスト、画像、スクリプトのカスタム記法は、それぞれ`<A,B,C>`の形式で重複掛けすることができます。
Config.ymlで一斉適用されるカスタム記法がある場合、加算されて適用されます。

### 話者名&テキスト

`<$costom_name$>`

### テキスト

ルビ：テキスト前`<テキスト|ルビ>`テキスト後

下線：テキスト前`<テキスト|U>`テキスト後

色：テキスト前`<テキスト|#ff0000>`テキスト後

サイズ：テキスト前`<テキスト|S120>`テキスト後

上下中央揃え：テキスト前`<テキスト|C>`テキスト後

### 画像

拡大：`<filename|S150>`

モノクロ：`<filename|M>`

位置変更`<filename|X100,Y130>`

### スクリプト（単位はms）

テキスト背景を透過：`<text_back_off>`

クリックディレイを制御：`<CLICK_DELAY=1000>`

自動シーンチェンジ時間をオーバーライド：`<AUTO_SCENE_CHANGE_DELAY=5000>`

## Config.ymlでの制御について

大きく以下の要素をConfigで指定できます。

1. タイトル（タブネームに反映）
2. タイトル画面の背景
3. タイトル画面のBGM
4. favicon
5. ローカルストレージのPrefix
6. デフォルトボリューム
7. クリックディレイ
8. オートシーンチェンジのデフォルト速度
9. 全画像に適用される一斉カスタム記法
10. インポートするWebフォントのURL
11. テーマカラー
12. 利用規約
13. クレジット欄及びURL

## ライセンス

Apache 2.0

## トラブルシューティング

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

## 将来の拡張予定

- スクリプト機能の拡充
- 効果音の適用
- カスタム記法の拡充

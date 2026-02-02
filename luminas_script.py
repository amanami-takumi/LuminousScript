#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LuminasScript - Visual Novel Game Generator
CSVファイルからビジュアルノベル形式のウェブゲームを生成します。
"""

import csv
import base64
import os
import json
import yaml
from pathlib import Path
from typing import List, Dict, Optional


class LuminasScript:
    """CSVからビジュアルノベルゲームを生成するメインクラス"""
    
    def __init__(self, input_dir: str = "input", output_dir: str = "output"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.assets_dir = self.input_dir / "assets"
        self.scenario_data: List[Dict] = []
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """config.ymlを読み込む"""
        config_path = self.input_dir / "config.yml"
        default_config = {
            'adv_title': 'LuminasScript Game',
            'adv_sub_title': '',
            'title_bg_image': '',
            'creator_name': '',
            'theme_color': '#667EEA',
            'sub_color': '#754CA3',
            'text_color': '#FFFFFF',
            'text_font_importURL': '',
            'x_account_url': '',
            'vrchat_account_url': '',
            'fediverse_account_url': '',
            'web_url': '',
            'booth_url': '',
            'favicon_url': ''
        }
        
        if not config_path.exists():
            print("⚠ config.ymlが見つかりません。デフォルト設定を使用します。")
            return default_config
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config:
                    default_config.update(config)
                print("✓ config.ymlを読み込みました")
                return default_config
        except Exception as e:
            print(f"⚠ config.ymlの読み込みに失敗しました: {e}")
            return default_config
        
    def load_csv(self, csv_filename: str = "scenario.csv") -> None:
        """CSVファイルを読み込む"""
        csv_path = self.input_dir / csv_filename
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
        
        # 複数のエンコーディングを試す
        encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'shift-jis', 'cp932']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    # 最初の行を読んで区切り文字を推測
                    sample = f.read(1024)
                    f.seek(0)
                    
                    # 区切り文字を検出
                    sniffer = csv.Sniffer()
                    try:
                        dialect = sniffer.sniff(sample, delimiters=',\t ')
                        reader = csv.DictReader(f, dialect=dialect)
                    except:
                        # 検出失敗時はデフォルトでカンマ区切り
                        reader = csv.DictReader(f)
                    
                    self.scenario_data = list(reader)
                    
                    # データが正しく読み込まれたか確認
                    if self.scenario_data and 'scene_id' in self.scenario_data[0]:
                        print(f"✓ {len(self.scenario_data)}行のシナリオデータを読み込みました (encoding: {encoding})")
                        return
                    
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"⚠ エンコーディング {encoding} で読み込み失敗: {e}")
                continue
        
        raise ValueError(f"CSVファイルのエンコーディングを検出できませんでした: {csv_path}")
    
    def encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """画像ファイルをBase64エンコードする"""
        if not image_path.exists():
            print(f"⚠ 画像が見つかりません: {image_path}")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                ext = image_path.suffix.lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }.get(ext, 'image/png')
                
                return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"⚠ 画像のエンコードに失敗: {image_path} - {e}")
            return None
    
    def collect_assets(self) -> Dict[str, str]:
        """使用されているすべてのアセットを収集してBase64エンコード"""
        assets = {}
        
        def get_image_path(directory: Path, filename: str) -> Optional[Path]:
            """画像ファイルのパスを取得（拡張子の自動補完付き）"""
            if not filename:
                return None
            
            # 拡張子がない場合は.pngを追加
            if not Path(filename).suffix:
                filename = filename + '.png'
            
            path = directory / filename
            if path.exists():
                return path
            
            # 拡張子なしでも試す
            path_without_ext = directory / Path(filename).stem
            if path_without_ext.exists():
                return path_without_ext
            
            return None
        
        # 背景画像
        bg_dir = self.assets_dir / "backgrounds"
        if bg_dir.exists():
            for row in self.scenario_data:
                bg_name = row.get('background_image', '').strip()
                if bg_name and bg_name not in assets:
                    bg_path = get_image_path(bg_dir, bg_name)
                    if bg_path:
                        encoded = self.encode_image_to_base64(bg_path)
                        if encoded:
                            assets[bg_name] = encoded
            
            # タイトル背景
            title_bg = self.config.get('title_bg_image', '').strip()
            if title_bg and title_bg not in assets:
                bg_path = get_image_path(bg_dir, title_bg)
                if bg_path:
                    encoded = self.encode_image_to_base64(bg_path)
                    if encoded:
                        assets[title_bg] = encoded
        
        # キャラクター立ち絵
        char_dir = self.assets_dir / "characters"
        if char_dir.exists():
            for row in self.scenario_data:
                for pos in ['center_standing_portrait_image', 'left_standing_portrait_image', 'right_standing_portrait_image']:
                    char_name = row.get(pos, '').strip()
                    if char_name and char_name not in assets:
                        char_path = get_image_path(char_dir, char_name)
                        if char_path:
                            encoded = self.encode_image_to_base64(char_path)
                            if encoded:
                                assets[char_name] = encoded
        
        print(f"✓ {len(assets)}個のアセットをエンコードしました")
        return assets
    
    def generate_html(self, output_filename: str = "game.html") -> None:
        """HTMLファイルを生成"""
        if not self.scenario_data:
            raise ValueError("シナリオデータが読み込まれていません")
        
        # アセットを収集
        assets = self.collect_assets()
        
        # シナリオデータをJSON形式に変換
        scenario_json = json.dumps(self.scenario_data, ensure_ascii=False, indent=2)
        assets_json = json.dumps(assets, ensure_ascii=False)
        config_json = json.dumps(self.config, ensure_ascii=False)
        
        # HTMLテンプレートを生成
        html_content = self._generate_html_template(scenario_json, assets_json, config_json)
        
        # 出力ディレクトリを作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイルに書き込み
        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ ゲームファイルを生成しました: {output_path}")
        print(f"  ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")
    
    def _generate_html_template(self, scenario_json: str, assets_json: str, config_json: str) -> str:
        """HTMLテンプレートを生成"""
        font_import = ""
        if self.config.get('text_font_importURL'):
            font_import = f'<link href="{self.config["text_font_importURL"]}" rel="stylesheet">'
        
        favicon_link = ""
        if self.config.get('favicon_url'):
            favicon_link = f'<link rel="icon" href="{self.config["favicon_url"]}">'
        
        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.get('adv_title', 'LuminasScript Game')}</title>
    {font_import}
    {favicon_link}
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <!-- ローディング画面 -->
    <div id="loading-screen">
        <div class="loading-content">
            <div class="spinner"></div>
            <p class="loading-text">ローディング中...</p>
        </div>
    </div>

    <div id="game-container" class="hidden">
        <!-- タイトル画面 -->
        <div id="title-screen" class="screen active">
            <div class="title-content">
                <h1 class="game-title">{self.config.get('adv_title', 'LuminasScript')}</h1>
                {f'<p class="game-subtitle">{self.config.get("adv_sub_title")}</p>' if self.config.get('adv_sub_title') else ''}
                <div class="title-menu">
                    <button class="menu-btn" onclick="startNewGame()">ニューゲーム</button>
                    <button class="menu-btn" onclick="loadGame()">ロード</button>
                    <button class="menu-btn" onclick="showSettings()">設定</button>
                    <button class="menu-btn" onclick="showCredits()">クレジット</button>
                </div>
            </div>
        </div>
        
        <!-- ゲーム画面 -->
        <div id="game-screen" class="screen">
            <div id="background-layer" class="layer"></div>
            
            <div id="character-layer" class="layer">
                <div id="char-left" class="character-sprite"></div>
                <div id="char-center" class="character-sprite"></div>
                <div id="char-right" class="character-sprite"></div>
            </div>
            
            <div id="ui-layer" class="layer">
                <div id="text-box">
                    <div id="speaker-name"></div>
                    <div id="dialogue-text"></div>
                    <div id="click-gauge-container">
                        <div id="click-gauge"></div>
                    </div>
                </div>
                
                <div id="choice-box" class="hidden">
                    <div id="choices-container"></div>
                </div>
                
                <div id="control-buttons">
                    <button id="history-button" onclick="toggleHistory()" title="会話履歴">📜</button>
                    <button id="auto-button" onclick="toggleAuto()" title="自動">▶</button>
                    <button id="menu-button" onclick="toggleGameMenu()" title="メニュー">≡</button>
                </div>
            </div>
        </div>
        
        <!-- 会話履歴画面 -->
        <div id="history-screen" class="modal hidden">
            <div class="modal-content history-content">
                <h2>会話履歴</h2>
                <div id="history-list"></div>
                <button class="menu-btn" onclick="closeHistory()">閉じる</button>
            </div>
        </div>
        
        <!-- ゲーム中メニュー -->
        <div id="game-menu" class="modal hidden">
            <div class="modal-content">
                <h2>メニュー</h2>
                <button class="menu-btn" onclick="saveGame()">セーブ</button>
                <button class="menu-btn" onclick="loadGame()">ロード</button>
                <button class="menu-btn" onclick="showSettings()">設定</button>
                <button class="menu-btn" onclick="returnToTitle()">タイトルに戻る</button>
                <button class="menu-btn" onclick="closeGameMenu()">閉じる</button>
            </div>
        </div>
        
        <!-- 設定画面 -->
        <div id="settings-screen" class="modal hidden">
            <div class="modal-content">
                <h2>設定</h2>
                <div class="setting-item">
                    <label>テキスト速度</label>
                    <input type="range" id="text-speed" min="1" max="10" value="5">
                </div>
                <div class="setting-item">
                    <label>BGM音量</label>
                    <input type="range" id="bgm-volume" min="0" max="100" value="70">
                </div>
                <div class="setting-item">
                    <label>SE音量</label>
                    <input type="range" id="se-volume" min="0" max="100" value="70">
                </div>
                <button class="menu-btn" onclick="closeSettings()">閉じる</button>
            </div>
        </div>
        
        <!-- クレジット画面 -->
        <div id="credits-screen" class="modal hidden">
            <div class="modal-content">
                <h2>クレジット</h2>
                <div class="credits-content">
                    {f'<p><strong>制作者:</strong> {self.config.get("creator_name")}</p>' if self.config.get('creator_name') else ''}
                    {f'<p><a href="{self.config.get("x_account_url")}" target="_blank">X (Twitter)</a></p>' if self.config.get('x_account_url') else ''}
                    {f'<p><a href="{self.config.get("vrchat_account_url")}" target="_blank">VRChat</a></p>' if self.config.get('vrchat_account_url') else ''}
                    {f'<p><a href="{self.config.get("fediverse_account_url")}" target="_blank">Fediverse</a></p>' if self.config.get('fediverse_account_url') else ''}
                    {f'<p><a href="{self.config.get("web_url")}" target="_blank">Website</a></p>' if self.config.get('web_url') else ''}
                    {f'<p><a href="{self.config.get("booth_url")}" target="_blank">BOOTH</a></p>' if self.config.get('booth_url') else ''}
                    <hr>
                    <p><strong>Generated by Luminous Script</strong></p>
                    <p class="license-info">このスクリプトは Apache License 2.0 の下でライセンスされています。</p>
                    <p class="license-info">ライセンスはスクリプトにのみ適用され、生成されたコンテンツには適用されません。</p>
                </div>
                <button class="menu-btn" onclick="closeCredits()">閉じる</button>
            </div>
        </div>
    </div>
    
    <script>
        {self._get_javascript(scenario_json, assets_json, config_json)}
    </script>
</body>
</html>"""
    
    def _get_css(self) -> str:
        """CSSスタイルを返す"""
        theme_color = self.config.get('theme_color', '#667EEA')
        sub_color = self.config.get('sub_color', '#754CA3')
        text_color = self.config.get('text_color', '#FFFFFF')
        
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Kosugi Maru', 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
            overflow: hidden;
            background: #000;
            color: {text_color};
        }}
        
        /* ローディング画面 */
        #loading-screen {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: opacity 0.5s ease;
        }}
        
        #loading-screen.fade-out {{
            opacity: 0;
            pointer-events: none;
        }}
        
        .loading-content {{
            text-align: center;
            color: white;
        }}
        
        .spinner {{
            width: 60px;
            height: 60px;
            border: 5px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1.5rem;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .loading-text {{
            font-size: 1.5rem;
            font-weight: bold;
        }}
        
        #game-container {{
            width: 100vw;
            height: 100vh;
            position: relative;
            overflow: hidden;
        }}
        
        #game-container.hidden {{
            display: none;
        }}
        
        .screen {{
            position: absolute;
            width: 100%;
            height: 100%;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }}
        
        .screen.active {{
            opacity: 1;
            pointer-events: auto;
        }}
        
        /* タイトル画面 */
        #title-screen {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .title-content {{
            text-align: center;
            color: white;
        }}
        
        .game-title {{
            font-size: 4rem;
            margin-bottom: 1rem;
            text-shadow: 0 4px 8px rgba(0,0,0,0.3);
            animation: titlePulse 2s ease-in-out infinite;
        }}
        
        .game-subtitle {{
            font-size: 1.5rem;
            margin-bottom: 3rem;
            opacity: 0.9;
        }}
        
        @keyframes titlePulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}
        
        .title-menu {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
            align-items: center;
        }}
        
        /* ゲーム画面 */
        #game-screen {{
            background: #000;
        }}
        
        .layer {{
            position: absolute;
            width: 100%;
            height: 100%;
        }}
        
        #background-layer {{
            background-size: cover;
            background-position: center;
            transition: background-image 0.5s ease;
        }}
        
        #character-layer {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            padding: 0 5%;
            pointer-events: none;
        }}
        
        .character-sprite {{
            width: 50%;
            height: 90%;
            background-size: contain;
            background-position: bottom center;
            background-repeat: no-repeat;
            opacity: 0;
            transition: opacity 0.3s ease;
            transform: scale(3);
            transform-origin: bottom center;
        }}
        
        .character-sprite.visible {{
            opacity: 1;
        }}
        
        #ui-layer {{
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            pointer-events: none;
        }}
        
        #text-box {{
            background: rgba(0, 0, 0, 0.85);
            margin: 2rem;
            padding: 2rem;
            border-radius: 10px;
            color: white;
            min-height: 150px;
            pointer-events: auto;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            position: relative;
        }}
        
        #speaker-name {{
            font-size: 1.3rem;
            font-weight: bold;
            margin-bottom: 0.8rem;
            color: #ffd700;
        }}
        
        #dialogue-text {{
            font-size: 1.1rem;
            line-height: 1.8;
            white-space: pre-wrap;
        }}
        
        #click-gauge-container {{
            position: absolute;
            bottom: 0.5rem;
            right: 1rem;
            width: 100px;
            height: 4px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
            overflow: hidden;
        }}
        
        #click-gauge {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, {theme_color}, {sub_color});
            transition: width 0.1s linear;
        }}
        
        #choice-box {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.9);
            padding: 2rem;
            border-radius: 15px;
            min-width: 60%;
            pointer-events: auto;
        }}
        
        #choice-box.hidden {{
            display: none;
        }}
        
        #choices-container {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .choice-btn {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            color: white;
            border: none;
            padding: 1.2rem 2rem;
            font-size: 1.1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            text-align: left;
        }}
        
        .choice-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }}
        
        #control-buttons {{
            position: absolute;
            top: 1rem;
            right: 1rem;
            display: flex;
            gap: 0.5rem;
            pointer-events: auto;
        }}
        
        #control-buttons button {{
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: 2px solid white;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            font-size: 1.2rem;
            cursor: pointer;
            transition: background 0.3s;
        }}
        
        #control-buttons button:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
        
        #auto-button.active {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            border-color: {theme_color};
        }}
        
        /* モーダル */
        .modal {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }}
        
        .modal.hidden {{
            display: none;
        }}
        
        .modal-content {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            padding: 3rem;
            border-radius: 15px;
            color: white;
            min-width: 400px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }}
        
        .modal-content h2 {{
            margin-bottom: 2rem;
            text-align: center;
            font-size: 2rem;
        }}
        
        .history-content {{
            max-width: 800px;
        }}
        
        #history-list {{
            background: rgba(0, 0, 0, 0.3);
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            max-height: 60vh;
            overflow-y: auto;
        }}
        
        .history-item {{
            margin-bottom: 1.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .history-item:last-child {{
            border-bottom: none;
        }}
        
        .history-speaker {{
            font-weight: bold;
            color: #ffd700;
            margin-bottom: 0.5rem;
        }}
        
        .history-text {{
            line-height: 1.6;
        }}
        
        .setting-item {{
            margin-bottom: 1.5rem;
        }}
        
        .setting-item label {{
            display: block;
            margin-bottom: 0.5rem;
            font-size: 1.1rem;
        }}
        
        .setting-item input[type="range"] {{
            width: 100%;
        }}
        
        .credits-content {{
            text-align: center;
        }}
        
        .credits-content p {{
            margin-bottom: 1rem;
        }}
        
        .credits-content a {{
            color: white;
            text-decoration: underline;
        }}
        
        .credits-content hr {{
            margin: 2rem 0;
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.3);
        }}
        
        .license-info {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        
        /* ボタン */
        .menu-btn {{
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid white;
            padding: 1rem 2rem;
            font-size: 1.1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            margin-bottom: 0.8rem;
            backdrop-filter: blur(10px);
        }}
        
        .menu-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(255, 255, 255, 0.3);
        }}
        
        .menu-btn:active {{
            transform: translateY(0);
        }}
        """
    
    def _get_javascript(self, scenario_json: str, assets_json: str, config_json: str) -> str:
        """JavaScriptコードを返す"""
        return f"""
        // ゲームデータ
        const SCENARIO_DATA = {scenario_json};
        const ASSETS = {assets_json};
        const CONFIG = {config_json};
        
        // ゲーム状態
        let currentSceneIndex = 0;
        let conversationHistory = [];
        let isAutoMode = false;
        let autoModeTimeout = null;
        let clickDelayTimer = null;
        let canClick = false;
        const CLICK_DELAY = 500; // クリック可能になるまでの時間（ミリ秒）
        
        let gameState = {{
            currentSceneId: null,
            visitedScenes: [],
            choices: {{}},
            settings: {{
                textSpeed: 5,
                bgmVolume: 70,
                seVolume: 70
            }}
        }};
        
        // 初期化
        document.addEventListener('DOMContentLoaded', () => {{
            console.log('LuminasScript initialized');
            console.log(`Loaded ${{SCENARIO_DATA.length}} scenes`);
            console.log(`Loaded ${{Object.keys(ASSETS).length}} assets`);
            
            // 設定を読み込み
            loadSettings();
            
            // タイトル背景を設定
            const titleBg = CONFIG.title_bg_image;
            if (titleBg && ASSETS[titleBg]) {{
                document.getElementById('title-screen').style.backgroundImage = `url(${{ASSETS[titleBg]}})`;
            }}
            
            // ローディング完了
            setTimeout(() => {{
                document.getElementById('loading-screen').classList.add('fade-out');
                setTimeout(() => {{
                    document.getElementById('loading-screen').style.display = 'none';
                    document.getElementById('game-container').classList.remove('hidden');
                }}, 500);
            }}, 1000);
        }});
        
        // クリック遅延ゲージの更新
        function startClickDelay() {{
            canClick = false;
            const gauge = document.getElementById('click-gauge');
            gauge.style.width = '0%';
            
            let progress = 0;
            const interval = 10;
            const increment = (100 / CLICK_DELAY) * interval;
            
            if (clickDelayTimer) clearInterval(clickDelayTimer);
            
            clickDelayTimer = setInterval(() => {{
                progress += increment;
                gauge.style.width = Math.min(progress, 100) + '%';
                
                if (progress >= 100) {{
                    clearInterval(clickDelayTimer);
                    canClick = true;
                }}
            }}, interval);
        }}
        
        // 自動モードの切り替え
        function toggleAuto() {{
            isAutoMode = !isAutoMode;
            const btn = document.getElementById('auto-button');
            
            if (isAutoMode) {{
                btn.classList.add('active');
                autoAdvance();
            }} else {{
                btn.classList.remove('active');
                if (autoModeTimeout) {{
                    clearTimeout(autoModeTimeout);
                    autoModeTimeout = null;
                }}
            }}
        }}
        
        function autoAdvance() {{
            if (!isAutoMode) return;
            
            const delay = 3000; // 3秒後に自動で進む
            autoModeTimeout = setTimeout(() => {{
                if (isAutoMode && canClick) {{
                    loadScene(currentSceneIndex + 1);
                }}
            }}, delay);
        }}
        
        // 会話履歴の追加
        function addToHistory(speaker, text) {{
            if (text && text.trim()) {{
                conversationHistory.push({{ speaker, text }});
            }}
        }}
        
        // 会話履歴の表示
        function toggleHistory() {{
            const historyScreen = document.getElementById('history-screen');
            const historyList = document.getElementById('history-list');
            
            historyList.innerHTML = '';
            conversationHistory.forEach(item => {{
                const div = document.createElement('div');
                div.className = 'history-item';
                
                if (item.speaker) {{
                    const speaker = document.createElement('div');
                    speaker.className = 'history-speaker';
                    speaker.textContent = item.speaker;
                    div.appendChild(speaker);
                }}
                
                const text = document.createElement('div');
                text.className = 'history-text';
                text.textContent = item.text;
                div.appendChild(text);
                
                historyList.appendChild(div);
            }});
            
            historyScreen.classList.remove('hidden');
            // 最新の履歴までスクロール
            historyList.scrollTop = historyList.scrollHeight;
        }}
        
        function closeHistory() {{
            document.getElementById('history-screen').classList.add('hidden');
        }}
        
        // ゲーム開始
        function startNewGame() {{
            currentSceneIndex = 0;
            conversationHistory = [];
            gameState.visitedScenes = [];
            gameState.choices = {{}};
            isAutoMode = false;
            document.getElementById('auto-button').classList.remove('active');
            
            showScreen('game-screen');
            loadScene(0);
        }}
        
        // シーンを読み込み
        function loadScene(index) {{
            if (index >= SCENARIO_DATA.length) {{
                console.log('Game finished');
                returnToTitle();
                return;
            }}
            
            // 自動モードのタイマーをクリア
            if (autoModeTimeout) {{
                clearTimeout(autoModeTimeout);
                autoModeTimeout = null;
            }}
            
            currentSceneIndex = index;
            const scene = SCENARIO_DATA[index];
            gameState.currentSceneId = scene.scene_id;
            gameState.visitedScenes.push(scene.scene_id);
            
            console.log(`Loading scene: ${{scene.scene_id}}`);
            
            // scene_idの解析
            const sceneType = getSceneType(scene.scene_id);
            
            if (sceneType === 'title') {{
                showChapterTitle(scene);
            }} else if (sceneType === 'choice') {{
                showChoices(scene);
            }} else {{
                showDialogue(scene);
            }}
        }}
        
        // scene_idのタイプを判定
        function getSceneType(sceneId) {{
            const parts = sceneId.split('-');
            if (parts.length >= 2) {{
                const type = parts[1];
                if (type === 'T') return 'title';
                if (type === 'Q') return 'choice';
                if (type === 'E') return 'ending';
            }}
            return 'dialogue';
        }}
        
        // チャプタータイトルを表示
        function showChapterTitle(scene) {{
            const textBox = document.getElementById('text-box');
            const speakerName = document.getElementById('speaker-name');
            const dialogueText = document.getElementById('dialogue-text');
            
            speakerName.textContent = '';
            dialogueText.textContent = scene.text || '';
            dialogueText.style.fontSize = '2.5rem';
            dialogueText.style.textAlign = 'center';
            dialogueText.style.fontWeight = 'bold';
            
            updateBackground(scene.background_image);
            clearCharacters();
            
            addToHistory('', scene.text);
            
            // 自動で次へ
            setTimeout(() => {{
                dialogueText.style.fontSize = '1.1rem';
                dialogueText.style.textAlign = 'left';
                dialogueText.style.fontWeight = 'normal';
                loadScene(currentSceneIndex + 1);
            }}, 2000);
        }}
        
        // 選択肢を表示
        function showChoices(scene) {{
            const choiceBox = document.getElementById('choice-box');
            const choicesContainer = document.getElementById('choices-container');
            const textBox = document.getElementById('text-box');
            
            textBox.style.display = 'none';
            choiceBox.classList.remove('hidden');
            choicesContainer.innerHTML = '';
            
            // テキストを選択肢に分割
            const choiceText = scene.text || '';
            const choices = choiceText.split('\\n').filter(c => c.trim());
            
            addToHistory('', '【選択肢】');
            
            choices.forEach((choice, index) => {{
                const btn = document.createElement('button');
                btn.className = 'choice-btn';
                btn.textContent = choice.trim();
                btn.onclick = () => selectChoice(scene.scene_id, index, choice);
                choicesContainer.appendChild(btn);
            }});
            
            updateBackground(scene.background_image);
        }}
        
        // 選択肢を選ぶ
        function selectChoice(sceneId, choiceIndex, choiceText) {{
            gameState.choices[sceneId] = {{ index: choiceIndex, text: choiceText }};
            
            addToHistory('', `→ ${{choiceText}}`);
            
            const choiceBox = document.getElementById('choice-box');
            const textBox = document.getElementById('text-box');
            
            choiceBox.classList.add('hidden');
            textBox.style.display = 'block';
            
            // 選択肢に応じた分岐を探す
            const branchLetter = String.fromCharCode(65 + choiceIndex); // A, B, C...
            const nextSceneId = sceneId.split('-')[0] + '-' + branchLetter + '-1';
            
            // 次のシーンを探す
            const nextIndex = SCENARIO_DATA.findIndex(s => s.scene_id === nextSceneId);
            if (nextIndex !== -1) {{
                loadScene(nextIndex);
            }} else {{
                // 見つからない場合は次のシーンへ
                loadScene(currentSceneIndex + 1);
            }}
        }}
        
        // 通常の会話を表示
        function showDialogue(scene) {{
            const speakerName = document.getElementById('speaker-name');
            const dialogueText = document.getElementById('dialogue-text');
            const textBox = document.getElementById('text-box');
            
            textBox.style.display = 'block';
            document.getElementById('choice-box').classList.add('hidden');
            
            speakerName.textContent = scene.person_name || '';
            
            // テキストを4行に制限
            let text = scene.text || '';
            const lines = text.split('\\n');
            if (lines.length > 4) {{
                text = lines.slice(0, 4).join('\\n');
            }}
            dialogueText.textContent = text;
            
            updateBackground(scene.background_image);
            updateCharacters(scene);
            
            addToHistory(scene.person_name, text);
            
            // クリック遅延を開始
            startClickDelay();
            
            // クリックで次へ
            textBox.onclick = () => {{
                if (canClick) {{
                    loadScene(currentSceneIndex + 1);
                }}
            }};
            
            // 自動モードの場合は自動で進む
            if (isAutoMode) {{
                autoAdvance();
            }}
        }}
        
        // 背景を更新
        function updateBackground(bgImage) {{
            const bgLayer = document.getElementById('background-layer');
            if (bgImage && ASSETS[bgImage]) {{
                bgLayer.style.backgroundImage = `url(${{ASSETS[bgImage]}})`;
            }}
        }}
        
        // キャラクターを更新
        function updateCharacters(scene) {{
            updateCharacter('char-left', scene.left_standing_portrait_image);
            updateCharacter('char-center', scene.center_standing_portrait_image);
            updateCharacter('char-right', scene.right_standing_portrait_image);
        }}
        
        function updateCharacter(elementId, imageName) {{
            const element = document.getElementById(elementId);
            if (imageName && ASSETS[imageName]) {{
                element.style.backgroundImage = `url(${{ASSETS[imageName]}})`;
                element.classList.add('visible');
            }} else {{
                element.style.backgroundImage = '';
                element.classList.remove('visible');
            }}
        }}
        
        function clearCharacters() {{
            ['char-left', 'char-center', 'char-right'].forEach(id => {{
                const element = document.getElementById(id);
                element.style.backgroundImage = '';
                element.classList.remove('visible');
            }});
        }}
        
        // 画面切り替え
        function showScreen(screenId) {{
            document.querySelectorAll('.screen').forEach(screen => {{
                screen.classList.remove('active');
            }});
            document.getElementById(screenId).classList.add('active');
        }}
        
        // セーブ/ロード
        function saveGame() {{
            try {{
                localStorage.setItem('luminas_save', JSON.stringify({{
                    sceneIndex: currentSceneIndex,
                    state: gameState,
                    history: conversationHistory
                }}));
                alert('セーブしました!');
                closeGameMenu();
            }} catch (e) {{
                alert('セーブに失敗しました: ' + e.message);
            }}
        }}
        
        function loadGame() {{
            try {{
                const saveData = localStorage.getItem('luminas_save');
                if (saveData) {{
                    const data = JSON.parse(saveData);
                    currentSceneIndex = data.sceneIndex;
                    gameState = data.state;
                    conversationHistory = data.history || [];
                    
                    showScreen('game-screen');
                    loadScene(currentSceneIndex);
                    closeGameMenu();
                }} else {{
                    alert('セーブデータがありません');
                }}
            }} catch (e) {{
                alert('ロードに失敗しました: ' + e.message);
            }}
        }}
        
        // 設定
        function loadSettings() {{
            const saved = localStorage.getItem('luminas_settings');
            if (saved) {{
                gameState.settings = JSON.parse(saved);
                document.getElementById('text-speed').value = gameState.settings.textSpeed;
                document.getElementById('bgm-volume').value = gameState.settings.bgmVolume;
                document.getElementById('se-volume').value = gameState.settings.seVolume;
            }}
        }}
        
        function saveSettings() {{
            gameState.settings.textSpeed = parseInt(document.getElementById('text-speed').value);
            gameState.settings.bgmVolume = parseInt(document.getElementById('bgm-volume').value);
            gameState.settings.seVolume = parseInt(document.getElementById('se-volume').value);
            localStorage.setItem('luminas_settings', JSON.stringify(gameState.settings));
        }}
        
        // メニュー操作
        function toggleGameMenu() {{
            const menu = document.getElementById('game-menu');
            menu.classList.toggle('hidden');
        }}
        
        function closeGameMenu() {{
            document.getElementById('game-menu').classList.add('hidden');
        }}
        
        function showSettings() {{
            document.getElementById('settings-screen').classList.remove('hidden');
            closeGameMenu();
        }}
        
        function closeSettings() {{
            saveSettings();
            document.getElementById('settings-screen').classList.add('hidden');
        }}
        
        function showCredits() {{
            document.getElementById('credits-screen').classList.remove('hidden');
        }}
        
        function closeCredits() {{
            document.getElementById('credits-screen').classList.add('hidden');
        }}
        
        function returnToTitle() {{
            showScreen('title-screen');
            closeGameMenu();
            isAutoMode = false;
            document.getElementById('auto-button').classList.remove('active');
        }}
        """


def main():
    """メイン処理"""
    import sys
    
    print("=" * 60)
    print("  LuminasScript - Visual Novel Game Generator")
    print("=" * 60)
    print()
    
    # コマンドライン引数の処理
    input_dir = "input"
    output_dir = "output"
    csv_file = "scenario.csv"
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    try:
        # ジェネレーターを初期化
        generator = LuminasScript(input_dir, output_dir)
        
        # CSVを読み込み
        generator.load_csv(csv_file)
        
        # HTMLを生成
        generator.generate_html()
        
        print()
        print("=" * 60)
        print("  ✓ 生成完了!")
        print("=" * 60)
        print()
        print(f"生成されたファイル: {output_dir}/game.html")
        print("ブラウザで開いてゲームをお楽しみください!")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

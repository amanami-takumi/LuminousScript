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
from datetime import datetime
from io import BytesIO
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
            'adv_text_title_off': '',
            'title_bg_image': '',
            'adv_title_music': '',
            'localstorage_prefix': '',
            'music_def_volume': '70',
            'creator_name': '',
            'License': '',
            'custom_name': '',
            'forbidden_word': [],
            'target_size': '',
            'optimization': '',
            'optimization_level': '',
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

        target_size = self._parse_target_size(self.config.get('target_size'))
        optimization_enabled = self._parse_bool(self.config.get('optimization'))
        optimization_level = self._parse_optimization_level(self.config.get('optimization_level'))

        if target_size or optimization_enabled:
            try:
                from PIL import Image
            except Exception as e:
                print(f"⚠ 画像の最適化にPillowが必要です。オリジナルで処理します: {e}")
                target_size = None
                optimization_enabled = False

        try:
            if target_size or optimization_enabled:
                with Image.open(image_path) as img:
                    img = img.convert("RGBA") if img.mode in ("P", "LA") else img
                    img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img

                    if target_size and img.width > target_size:
                        new_height = int(img.height * (target_size / img.width))
                        img = img.resize((target_size, new_height), Image.LANCZOS)

                    if optimization_enabled:
                        if optimization_level is not None:
                            payload, mime_type = self._encode_webp_with_quality(img, optimization_level)
                        else:
                            payload, mime_type = self._encode_webp_approx_200kb(img)
                    else:
                        payload, mime_type = self._encode_original_format(img, image_path.suffix.lower())
            else:
                with open(image_path, 'rb') as f:
                    payload = f.read()
                ext = image_path.suffix.lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }.get(ext, 'image/png')

            encoded = base64.b64encode(payload).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"⚠ 画像のエンコードに失敗: {image_path} - {e}")
            return None

    def encode_audio_to_base64(self, audio_path: Path) -> Optional[str]:
        """音声ファイルをBase64エンコードする"""
        if not audio_path.exists():
            print(f"⚠ 音声が見つかりません: {audio_path}")
            return None

        try:
            with open(audio_path, 'rb') as f:
                payload = f.read()

            ext = audio_path.suffix.lower()
            mime_type = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg',
                '.m4a': 'audio/mp4'
            }.get(ext, 'application/octet-stream')

            encoded = base64.b64encode(payload).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"⚠ 音声のエンコードに失敗: {audio_path} - {e}")
            return None

    def encode_file_to_data_url(self, file_path: Path, mime_type: str) -> Optional[str]:
        """任意ファイルをData URLへ変換する"""
        if not file_path.exists():
            print(f"⚠ ファイルが見つかりません: {file_path}")
            return None

        try:
            with open(file_path, 'rb') as f:
                payload = f.read()
            encoded = base64.b64encode(payload).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"⚠ ファイルのエンコードに失敗: {file_path} - {e}")
            return None

    def _parse_target_size(self, value) -> Optional[int]:
        """target_sizeを整数に変換"""
        if value is None:
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        text = str(value).strip()
        if not text:
            return None
        try:
            size = int(text)
            return size if size > 0 else None
        except ValueError:
            print(f"⚠ target_sizeが不正です: {value}")
            return None

    def _parse_bool(self, value) -> bool:
        """文字列・数値から真偽値を判定"""
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        return text in ("1", "true", "yes", "on")

    def _parse_volume(self, value, default: int = 70) -> int:
        """音量設定を0〜100の整数に変換"""
        if value is None:
            return default
        try:
            volume = int(str(value).strip())
        except (TypeError, ValueError):
            print(f"⚠ music_def_volumeが不正です: {value}")
            return default
        return min(max(volume, 0), 100)

    def _parse_optimization_level(self, value) -> Optional[int]:
        """optimization_levelを1〜99の整数に変換"""
        if value is None:
            return None
        if isinstance(value, int):
            return value if 1 <= value <= 99 else None
        text = str(value).strip()
        if not text:
            return None
        try:
            level = int(text)
        except ValueError:
            print(f"⚠ optimization_levelが不正です: {value}")
            return None
        return level if 1 <= level <= 99 else None

    def _encode_original_format(self, img, ext: str) -> (bytes, str):
        """元形式で画像をバイト列に変換"""
        buffer = BytesIO()
        if ext in ('.jpg', '.jpeg'):
            img.convert("RGB").save(buffer, format="JPEG", quality=95)
            mime_type = 'image/jpeg'
        elif ext == '.webp':
            img.save(buffer, format="WEBP", quality=90, method=6)
            mime_type = 'image/webp'
        elif ext == '.gif':
            img.save(buffer, format="GIF")
            mime_type = 'image/gif'
        else:
            img.save(buffer, format="PNG", optimize=True)
            mime_type = 'image/png'
        return buffer.getvalue(), mime_type

    def _encode_webp_with_quality(self, img, quality: int) -> (bytes, str):
        """WebPへ変換し、指定品質で出力"""
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=6)
        return buffer.getvalue(), 'image/webp'

    def _encode_webp_approx_200kb(self, img) -> (bytes, str):
        """WebPへ変換し、200KB程度まで品質を調整"""
        target_bytes = 200 * 1024
        quality = 90
        best_payload = None

        while quality >= 30:
            buffer = BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=6)
            payload = buffer.getvalue()
            best_payload = payload
            if len(payload) <= target_bytes:
                break
            quality -= 5

        return best_payload or b"", 'image/webp'
    
    def _find_asset_path(self, directory: Path, filename: str, default_extensions: List[str]) -> Optional[Path]:
        """アセットファイルのパスを取得（拡張子の自動補完付き）"""
        normalized = self._normalize_asset_reference(filename)
        if not normalized:
            return None

        candidate_names = [normalized]
        normalized_path = Path(normalized)
        if not normalized_path.suffix:
            candidate_names.extend(f"{normalized}{ext}" for ext in default_extensions)

        for candidate in candidate_names:
            path = directory / candidate
            if path.is_file():
                return path

        path_without_ext = normalized_path.with_suffix("")
        fallback_path = directory / path_without_ext
        if fallback_path.is_file():
            return fallback_path

        legacy_path = directory / normalized_path.stem
        if legacy_path.is_file():
            return legacy_path

        # サブディレクトリ指定がない場合は配下を再帰探索する
        if len(normalized_path.parts) == 1:
            recursive_matches: List[Path] = []
            seen_paths = set()

            search_names = candidate_names + [path_without_ext.name, legacy_path.name]
            for search_name in search_names:
                for path in sorted(directory.rglob(search_name)):
                    if not path.is_file():
                        continue
                    resolved = path.resolve()
                    if resolved in seen_paths:
                        continue
                    seen_paths.add(resolved)
                    recursive_matches.append(path)

            if recursive_matches:
                if len(recursive_matches) > 1:
                    match_list = ", ".join(str(path.relative_to(directory)) for path in recursive_matches[:3])
                    if len(recursive_matches) > 3:
                        match_list += ", ..."
                    print(
                        f"⚠ アセット '{filename}' に複数候補が見つかりました。"
                        f"先頭を使用します: {match_list}"
                    )
                return recursive_matches[0]

        return None

    def _normalize_asset_reference(self, filename: str) -> str:
        """CSV上のアセット参照を安全な相対パスへ正規化"""
        if not filename:
            return ""

        normalized = str(filename).strip().replace("\\", "/")
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        normalized = normalized.lstrip("/")
        if not normalized or normalized in {".", ".."}:
            return ""

        parts = []
        for part in normalized.split("/"):
            if not part or part == ".":
                continue
            if part == "..":
                print(f"⚠ アセット参照で親ディレクトリは使用できません: {filename}")
                return ""
            parts.append(part)

        return "/".join(parts)


    def collect_assets(self) -> Dict[str, Dict[str, str]]:
        """使用されているすべてのアセットを収集してBase64エンコード"""
        image_assets = {}
        audio_assets = {}
        
        # 背景画像
        bg_dir = self.assets_dir / "backgrounds"
        if bg_dir.exists():
            for row in self.scenario_data:
                bg_name_raw = row.get('background_image', '').strip()
                bg_name = self._extract_asset_name(bg_name_raw)
                if bg_name and bg_name not in image_assets:
                    bg_path = self._find_asset_path(bg_dir, bg_name, ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
                    if bg_path:
                        encoded = self.encode_image_to_base64(bg_path)
                        if encoded:
                            image_assets[bg_name] = encoded
            
            # タイトル背景
            title_bg_raw = self.config.get('title_bg_image', '').strip()
            title_bg = self._extract_asset_name(title_bg_raw)
            if title_bg and title_bg not in image_assets:
                bg_path = self._find_asset_path(bg_dir, title_bg, ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
                if bg_path:
                    encoded = self.encode_image_to_base64(bg_path)
                    if encoded:
                        image_assets[title_bg] = encoded
        
        # キャラクター立ち絵
        char_dir = self.assets_dir / "characters"
        if char_dir.exists():
            for row in self.scenario_data:
                for pos in ['center_standing_portrait_image', 'left_standing_portrait_image', 'right_standing_portrait_image']:
                    char_name_raw = row.get(pos, '').strip()
                    char_name = self._extract_asset_name(char_name_raw)
                    if char_name and char_name not in image_assets:
                        char_path = self._find_asset_path(char_dir, char_name, ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
                        if char_path:
                            encoded = self.encode_image_to_base64(char_path)
                            if encoded:
                                image_assets[char_name] = encoded

        # BGM
        bgm_dir = self.assets_dir / "bgms"
        if bgm_dir.exists():
            for row in self.scenario_data:
                bgm_name_raw = row.get('bgm', '').strip()
                bgm_name = self._extract_asset_name(bgm_name_raw)
                if bgm_name and bgm_name not in audio_assets:
                    bgm_path = self._find_asset_path(bgm_dir, bgm_name, ['.mp3', '.wav', '.ogg', '.m4a'])
                    if bgm_path:
                        encoded = self.encode_audio_to_base64(bgm_path)
                        if encoded:
                            audio_assets[bgm_name] = encoded

            title_bgm_raw = self.config.get('adv_title_music', '').strip()
            title_bgm = self._extract_asset_name(title_bgm_raw)
            if title_bgm and title_bgm not in audio_assets:
                bgm_path = self._find_asset_path(bgm_dir, title_bgm, ['.mp3', '.wav', '.ogg', '.m4a'])
                if bgm_path:
                    encoded = self.encode_audio_to_base64(bgm_path)
                    if encoded:
                        audio_assets[title_bgm] = encoded

        print(f"✓ 画像{len(image_assets)}個 / 音声{len(audio_assets)}個のアセットをエンコードしました")
        return {
            'images': image_assets,
            'audio': audio_assets
        }

    def _extract_asset_name(self, spec: str) -> str:
        """<FileName|...>形式からファイル名を抽出"""
        if not spec:
            return ''
        text = str(spec).strip()
        if len(text) >= 2 and text.startswith('<') and text.endswith('>'):
            inner = text[1:-1].strip()
            if '|' in inner:
                return inner.split('|', 1)[0].strip()
            return inner
        return text

    def _resolve_favicon_href(self) -> str:
        """favicon_urlを単一HTMLで使えるhrefへ解決"""
        raw = str(self.config.get('favicon_url') or '').strip()
        if not raw:
            return ''

        lowered = raw.lower()
        if lowered.startswith(('data:', 'http://', 'https://')):
            return raw

        branding_dir = self.assets_dir / "branding"
        favicon_path = None
        if branding_dir.exists():
            favicon_path = self._find_asset_path(
                branding_dir,
                raw,
                ['.ico', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg']
            )

        if not favicon_path:
            input_candidate = self.input_dir / raw
            if input_candidate.is_file():
                favicon_path = input_candidate

        if not favicon_path:
            print(f"⚠ favicon が見つかりません: {raw}")
            return ''

        mime_type = {
            '.ico': 'image/x-icon',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }.get(favicon_path.suffix.lower(), 'application/octet-stream')

        encoded = self.encode_file_to_data_url(favicon_path, mime_type)
        return encoded or ''
    
    def generate_html(self, output_filename: str = "game.html", latest_filename: Optional[str] = None) -> None:
        """HTMLファイルを生成"""
        if not self.scenario_data:
            raise ValueError("シナリオデータが読み込まれていません")
        
        # アセットを収集
        assets = self.collect_assets()
        
        # シナリオデータをJSON形式に変換
        scenario_json = json.dumps(self.scenario_data, ensure_ascii=False, indent=2)
        image_assets_json = json.dumps(assets['images'], ensure_ascii=False)
        audio_assets_json = json.dumps(assets['audio'], ensure_ascii=False)
        config_json = json.dumps(self.config, ensure_ascii=False)
        
        # HTMLテンプレートを生成
        html_content = self._generate_html_template(scenario_json, image_assets_json, audio_assets_json, config_json)
        
        # 出力ディレクトリを作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイルに書き込み
        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ ゲームファイルを生成しました: {output_path}")

        if latest_filename and latest_filename != output_filename:
            latest_path = self.output_dir / latest_filename
            with open(latest_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✓ 最新版を更新しました: {latest_path}")

        print(f"  ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")
    
    def _generate_html_template(self, scenario_json: str, image_assets_json: str, audio_assets_json: str, config_json: str) -> str:
        """HTMLテンプレートを生成"""
        default_volume = self._parse_volume(self.config.get('music_def_volume'))
        show_title_text = not self._parse_bool(self.config.get('adv_text_title_off'))
        font_import = ""
        if self.config.get('text_font_importURL'):
            font_import = f'<link href="{self.config["text_font_importURL"]}" rel="stylesheet">'
        
        favicon_link = ""
        favicon_href = self._resolve_favicon_href()
        if favicon_href:
            favicon_link = f'<link rel="icon" href="{favicon_href}">'
        
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
                {f'<h1 class="game-title">{self.config.get("adv_title", "LuminasScript")}</h1>' if show_title_text else ''}
                {f'<p class="game-subtitle">{self.config.get("adv_sub_title")}</p>' if show_title_text and self.config.get('adv_sub_title') else ''}
                <div class="title-menu">
                    <button class="menu-btn" onclick="startNewGame()">ニューゲーム</button>
                    <button class="menu-btn" onclick="loadGame()">ロード</button>
                    <button class="menu-btn" onclick="showSettings()">設定</button>
                    <button class="menu-btn" onclick="showCredits()">クレジット</button>
                </div>
            </div>
            {f'<div class="title-version">{self.config.get("version")}</div>' if self.config.get('version') else ''}
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
                    <input type="range" id="bgm-volume" min="0" max="100" value="{default_volume}">
                </div>
                <div class="setting-item">
                    <label>SE音量</label>
                    <input type="range" id="se-volume" min="0" max="100" value="{default_volume}">
                </div>
                <div id="custom-name-setting" class="setting-item hidden">
                    <label>ユーザー名</label>
                    <input type="text" id="custom-name-input" class="text-input" placeholder="ユーザー名を入力">
                    <p class="input-help">ハイフンやスペースなどの記号は無視されます。</p>
                </div>
                <button class="menu-btn" onclick="closeSettings()">閉じる</button>
            </div>
        </div>

        <!-- ライセンス同意 -->
        <div id="license-modal" class="modal hidden">
            <div class="modal-content license-content">
                <h2>ライセンス</h2>
                <div id="license-text" class="license-text"></div>
                <div class="license-actions">
                    <button class="menu-btn" onclick="acceptLicense()">同意して開始</button>
                    <button class="menu-btn" onclick="declineLicense()">同意しない</button>
                </div>
            </div>
        </div>

        <!-- ユーザー名設定 -->
        <div id="custom-name-modal" class="modal hidden">
            <div class="modal-content">
                <h2>ユーザー名設定</h2>
                <div class="setting-item">
                    <label>ユーザー名</label>
                    <input type="text" id="custom-name-modal-input" class="text-input" placeholder="ユーザー名を入力">
                    <p class="input-help">ハイフンやスペースなどの記号は無視されます。</p>
                    <p id="custom-name-error" class="input-error hidden"></p>
                </div>
                <div class="license-actions">
                    <button class="menu-btn" onclick="confirmCustomName()">決定</button>
                    <button class="menu-btn" onclick="skipCustomName()">後で設定</button>
                </div>
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
                    {f'''
                    <div class="credits-license">
                        <p><strong>ライセンス:</strong></p>
                        <button class="menu-btn" onclick="showLicenseModal(true)">ライセンスを表示</button>
                    </div>
                    ''' if (self.config.get('License') or self.config.get('license') or '').strip() else ''}
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
        {self._get_javascript(scenario_json, image_assets_json, audio_assets_json, config_json)}
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

        .hidden {{
            display: none !important;
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
            display: none;
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }}
        
        .screen.active {{
            display: block;
            opacity: 1;
            visibility: visible;
            pointer-events: auto;
        }}
        
        /* タイトル画面 */
        #title-screen {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            align-items: center;
            justify-content: center;
            position: relative;
        }}

        #title-screen.active {{
            display: flex;
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
            margin-top: 20rem;
        }}

        .title-version {{
            position: absolute;
            right: 1.5rem;
            bottom: 1rem;
            color: rgba(255, 255, 255, 0.45);
            font-size: 0.9rem;
            letter-spacing: 0.08em;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
            pointer-events: none;
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
            z-index: 0;
        }}
        
        #character-layer {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            padding: 0 5%;
            pointer-events: none;
            z-index: 1;
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
            z-index: 2;
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

        .license-content {{
            max-width: 720px;
        }}

        .license-text {{
            background: rgba(0, 0, 0, 0.25);
            padding: 1.2rem;
            border-radius: 10px;
            line-height: 1.6;
            white-space: pre-wrap;
            max-height: 50vh;
            overflow-y: auto;
            margin-bottom: 1.5rem;
        }}

        .license-actions {{
            display: flex;
            gap: 0.8rem;
            justify-content: center;
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

        .text-input {{
            width: 100%;
            padding: 0.8rem 1rem;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.4);
            background: rgba(0, 0, 0, 0.2);
            color: white;
            font-size: 1rem;
        }}

        .input-help {{
            margin-top: 0.5rem;
            font-size: 0.85rem;
            opacity: 0.8;
        }}

        .input-error {{
            margin-top: 0.6rem;
            font-size: 0.9rem;
            color: #ffd0d0;
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

        .credits-license {{
            margin: 1rem 0 0.5rem;
        }}

        .credits-license .menu-btn {{
            margin-top: 0.4rem;
        }}
        
        .license-info {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        
        /* ボタン */
        .menu-btn {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            color: white;
            border: 2px solid white;
            padding: 1rem 8rem;
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
    
    def _get_javascript(self, scenario_json: str, image_assets_json: str, audio_assets_json: str, config_json: str) -> str:
        """JavaScriptコードを返す"""
        default_volume = self._parse_volume(self.config.get('music_def_volume'))
        return f"""
        // ゲームデータ
        const SCENARIO_DATA = {scenario_json};
        const ASSETS = {image_assets_json};
        const AUDIO_ASSETS = {audio_assets_json};
        const CONFIG = {config_json};
        const DEFAULT_SETTINGS = {{
            textSpeed: 5,
            bgmVolume: {default_volume},
            seVolume: {default_volume},
            customName: ''
        }};
        const BGM_FADE_DURATION = 1000;
        const STORAGE_PREFIX = normalizeStoragePrefix(
            CONFIG.localstorage_prefix ?? CONFIG.localStoragePrefix
        );
        const SAVE_DATA_KEY = getStorageKey('luminas_save');
        const SETTINGS_KEY = getStorageKey('luminas_settings');
        
        // ゲーム状態
        let currentSceneIndex = 0;
        let conversationHistory = [];
        let isAutoMode = false;
        let autoModeTimeout = null;
        let clickDelayTimer = null;
        let canClick = false;
        const CLICK_DELAY = 500; // クリック可能になるまでの時間（ミリ秒）
        let licenseAccepted = false;
        const LICENSE_ACCEPT_KEY = getStorageKey('luminas_license_accepted');
        let bgmAudio = null;
        let bgmFadeInterval = null;
        let currentBgmName = '';
        
        let gameState = {{
            currentSceneId: null,
            visitedScenes: [],
            choices: {{}},
            settings: {{
                textSpeed: 5,
                bgmVolume: {default_volume},
                seVolume: {default_volume},
                customName: ''
            }}
        }};
        
        // 初期化
        document.addEventListener('DOMContentLoaded', () => {{
            console.log('LuminasScript initialized');
            console.log(`Loaded ${{SCENARIO_DATA.length}} scenes`);
            console.log(`Loaded ${{Object.keys(ASSETS).length}} assets`);
            console.log(`Loaded ${{Object.keys(AUDIO_ASSETS).length}} bgm assets`);
            
            // 設定を読み込み
            loadSettings();
            loadLicenseAcceptance();
            initCustomNameUI();
            
            // タイトル背景を設定
            const titleBg = extractAssetName(CONFIG.title_bg_image);
            if (titleBg && ASSETS[titleBg]) {{
                document.getElementById('title-screen').style.backgroundImage = `url(${{ASSETS[titleBg]}})`;
            }}
            
            // ローディング完了
            setTimeout(() => {{
                document.getElementById('loading-screen').classList.add('fade-out');
                setTimeout(() => {{
                    document.getElementById('loading-screen').style.display = 'none';
                    document.getElementById('game-container').classList.remove('hidden');
                    activateTitleScreen();
                    if (isLicenseRequired() && !licenseAccepted) {{
                        showLicenseModal(true);
                    }} else {{
                        maybePromptCustomName();
                    }}
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
                    loadScene(findNextSceneIndex(currentSceneIndex));
                }}
            }}, delay);
        }}

        function normalizeSceneId(sceneId) {{
            return (sceneId || '').trim();
        }}

        function extractAssetName(spec) {{
            const text = String(spec || '').trim();
            if (text.startsWith('<') && text.endsWith('>')) {{
                const inner = text.slice(1, -1).trim();
                const separatorIndex = inner.indexOf('|');
                return (separatorIndex >= 0 ? inner.slice(0, separatorIndex) : inner).trim();
            }}
            return text;
        }}

        function normalizeStoragePrefix(value) {{
            return String(value || '').trim().replace(/^_+|_+$/g, '');
        }}

        function getStorageKey(name) {{
            return STORAGE_PREFIX ? `${{STORAGE_PREFIX}}_${{name}}` : name;
        }}

        function safeStorageGet(key) {{
            try {{
                return localStorage.getItem(key);
            }} catch (e) {{
                console.warn(`localStorage read failed for ${{key}}:`, e);
                return null;
            }}
        }}

        function safeStorageSet(key, value) {{
            try {{
                localStorage.setItem(key, value);
                return true;
            }} catch (e) {{
                console.warn(`localStorage write failed for ${{key}}:`, e);
                return false;
            }}
        }}

        function safeStorageRemove(key) {{
            try {{
                localStorage.removeItem(key);
                return true;
            }} catch (e) {{
                console.warn(`localStorage remove failed for ${{key}}:`, e);
                return false;
            }}
        }}

        function escapeHtml(text) {{
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }}

        function formatText(raw) {{
            if (!raw) return '';
            const src = String(raw);
            const token = /<([^|<>]+)\\|([^<>]+)>/g;
            let result = '';
            let lastIndex = 0;
            let match;

            while ((match = token.exec(src)) !== null) {{
                result += escapeHtml(src.slice(lastIndex, match.index));
                const body = match[1];
                const styleRaw = match[2].trim();
                const safeText = escapeHtml(body);
                const parts = styleRaw.split(',').map(s => s.trim()).filter(Boolean);
                let color = null;
                let underline = false;
                let ruby = null;

                parts.forEach(p => {{
                    if (/^#([0-9a-fA-F]{{3}}|[0-9a-fA-F]{{6}})$/.test(p)) {{
                        if (!color) color = p;
                    }} else if (p.toUpperCase() === 'U') {{
                        underline = true;
                    }} else if (!ruby) {{
                        ruby = p;
                    }}
                }});

                let formatted = safeText;
                if (ruby) {{
                    const safeRuby = escapeHtml(ruby);
                    formatted = `<ruby>${{formatted}}<rt>${{safeRuby}}</rt></ruby>`;
                }}
                if (underline) {{
                    formatted = `<span style="text-decoration: underline;">${{formatted}}</span>`;
                }}
                if (color) {{
                    formatted = `<span style="color:${{color}}">${{formatted}}</span>`;
                }}
                result += formatted;

                lastIndex = token.lastIndex;
            }}

            result += escapeHtml(src.slice(lastIndex));
            return result.replace(/\\n/g, '<br>');
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
                text.innerHTML = formatText(item.text);
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
            if (isLicenseRequired() && !licenseAccepted) {{
                showLicenseModal(true);
                return;
            }}
            currentSceneIndex = 0;
            conversationHistory = [];
            gameState.visitedScenes = [];
            gameState.choices = {{}};
            isAutoMode = false;
            document.getElementById('auto-button').classList.remove('active');
            
            showScreen('game-screen');
            loadScene(0);
        }}

        function resetSceneUI() {{
            const textBox = document.getElementById('text-box');
            const choiceBox = document.getElementById('choice-box');
            const dialogueText = document.getElementById('dialogue-text');

            textBox.style.display = 'block';
            choiceBox.classList.add('hidden');
            dialogueText.style.fontSize = '1.1rem';
            dialogueText.style.textAlign = 'left';
            dialogueText.style.fontWeight = 'normal';
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
            const sceneId = normalizeSceneId(scene.scene_id);
            gameState.currentSceneId = sceneId;
            gameState.visitedScenes.push(sceneId);
            resetSceneUI();
            updateBgm(scene.bgm);
            
            console.log(`Loading scene: ${{sceneId}}`);
            
            // scene_idの解析
            const sceneType = getSceneType(sceneId);
            
            if (sceneType === 'title') {{
                showChapterTitle(scene);
            }} else if (sceneType === 'choice') {{
                showChoices(scene);
            }} else if (sceneType === 'ending') {{
                showEnding(scene);
            }} else {{
                showDialogue(scene);
            }}
        }}
        
        // scene_idのタイプを判定
        function getSceneType(sceneId) {{
            const parts = normalizeSceneId(sceneId).split('-');
            if (parts.length >= 2) {{
                const last = parts[parts.length - 1];
                const second = parts[1];
                if (last === 'T' || second === 'T') return 'title';
                if (last === 'Q' || second === 'Q') return 'choice';
                if (last === 'E' || second === 'E') return 'ending';
            }}
            return 'dialogue';
        }}

        function isBranchRoute(sceneId) {{
            const parts = normalizeSceneId(sceneId).split('-');
            if (parts.length < 3) return false;
            const branch = parts[1];
            return /^[A-Z]$/.test(branch) && branch !== 'M' && branch !== 'Q' && branch !== 'T' && branch !== 'E';
        }}

        function findNextSceneIndex(currentIndex) {{
            const currentScene = SCENARIO_DATA[currentIndex];
            if (!currentScene || !currentScene.scene_id) return currentIndex + 1;
            
            const sceneId = normalizeSceneId(currentScene.scene_id);
            if (!isBranchRoute(sceneId)) return currentIndex + 1;
            
            const parts = sceneId.split('-');
            const chapter = parts[0];
            const branch = parts[1];
            const branchPrefix = `${{chapter}}-${{branch}}-`;
            
            for (let i = currentIndex + 1; i < SCENARIO_DATA.length; i++) {{
                const id = normalizeSceneId(SCENARIO_DATA[i].scene_id);
                if (id.startsWith(branchPrefix)) return i;
            }}
            
            const mergePrefix = `${{chapter}}-M-`;
            const mergeIndex = SCENARIO_DATA.findIndex(s => {{
                const id = normalizeSceneId(s.scene_id);
                return id === `${{chapter}}-M` || id.startsWith(mergePrefix);
            }});
            if (mergeIndex !== -1 && mergeIndex > currentIndex) {{
                return mergeIndex;
            }}
            
            return currentIndex + 1;
        }}
        
        // チャプタータイトルを表示
        function showChapterTitle(scene) {{
            const textBox = document.getElementById('text-box');
            const speakerName = document.getElementById('speaker-name');
            const dialogueText = document.getElementById('dialogue-text');
            
            speakerName.textContent = '';
            const chapterText = applyCustomName(scene.text || '');
            dialogueText.innerHTML = formatText(chapterText);
            dialogueText.style.fontSize = '2.5rem';
            dialogueText.style.textAlign = 'center';
            dialogueText.style.fontWeight = 'bold';
            
            updateBackground(scene.background_image);
            clearCharacters();
            
            addToHistory('', chapterText);
            
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
            const choiceText = applyCustomName(scene.text || '');
            const choices = choiceText.split('\\n').filter(c => c.trim());
            
            addToHistory('', '【選択肢】');
            
            choices.forEach((choice, index) => {{
                const btn = document.createElement('button');
                btn.className = 'choice-btn';
                const trimmedChoice = choice.trim();
                btn.innerHTML = formatText(trimmedChoice);
                btn.onclick = () => selectChoice(scene.scene_id, index, trimmedChoice);
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
            const parts = normalizeSceneId(sceneId).split('-');
            const baseParts = parts.slice(0, -1);
            const nextSceneId = baseParts.concat(branchLetter, '1').join('-');
            
            // 次のシーンを探す
            const nextIndex = SCENARIO_DATA.findIndex(s => normalizeSceneId(s.scene_id) === nextSceneId);
            if (nextIndex !== -1) {{
                loadScene(nextIndex);
            }} else {{
                // 見つからない場合は次のシーンへ
                loadScene(currentSceneIndex + 1);
            }}
        }}

        function showEnding(scene) {{
            const speakerName = document.getElementById('speaker-name');
            const dialogueText = document.getElementById('dialogue-text');
            const textBox = document.getElementById('text-box');

            textBox.style.display = 'block';
            document.getElementById('choice-box').classList.add('hidden');

            speakerName.textContent = scene.person_name || '';

            let text = applyCustomName(scene.text || '');
            const lines = text.split('\\n');
            if (lines.length > 4) {{
                text = lines.slice(0, 4).join('\\n');
            }}
            dialogueText.innerHTML = formatText(text);

            updateBackground(scene.background_image);
            updateCharacters(scene);

            addToHistory(scene.person_name, text);

            startClickDelay();
            textBox.onclick = () => {{
                if (canClick) {{
                    returnToTitle();
                }}
            }};

            if (isAutoMode) {{
                autoModeTimeout = setTimeout(() => {{
                    if (isAutoMode) {{
                        returnToTitle();
                    }}
                }}, 3000);
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
            let text = applyCustomName(scene.text || '');
            const lines = text.split('\\n');
            if (lines.length > 4) {{
                text = lines.slice(0, 4).join('\\n');
            }}
            dialogueText.innerHTML = formatText(text);
            
            updateBackground(scene.background_image);
            updateCharacters(scene);
            
            addToHistory(scene.person_name, text);
            
            // クリック遅延を開始
            startClickDelay();
            
            // クリックで次へ
            textBox.onclick = () => {{
                if (canClick) {{
                    loadScene(findNextSceneIndex(currentSceneIndex));
                }}
            }};
            
            // 自動モードの場合は自動で進む
            if (isAutoMode) {{
                autoAdvance();
            }}
        }}

        const CHARACTER_BASE_SCALE = 3;
        const BACKGROUND_BASE_SCALE = 1;

        function normalizeEffectToken(token) {{
            return token.replace(/[‐‑‒–—−]/g, '-');
        }}

        function parseImageSpec(spec) {{
            if (!spec) {{
                return {{ name: '', effects: null }};
            }}
            const trimmed = String(spec).trim();
            if (!(trimmed.startsWith('<') && trimmed.endsWith('>'))) {{
                return {{ name: trimmed, effects: null }};
            }}

            const inner = trimmed.slice(1, -1).trim();
            const parts = inner.split('|');
            const name = (parts[0] || '').trim();
            const effects = {{
                monochrome: false,
                scale: 100,
                offsetX: 0,
                offsetY: 0,
                vibration: 0
            }};

            if (parts[1]) {{
                const tokens = parts[1].split(',').map(t => normalizeEffectToken(t.trim())).filter(Boolean);
                tokens.forEach(token => {{
                    if (token === 'M') {{
                        effects.monochrome = true;
                        return;
                    }}
                    if (token.startsWith('S')) {{
                        const value = parseFloat(token.slice(1));
                        if (!Number.isNaN(value) && value > 0) {{
                            effects.scale = value;
                        }}
                        return;
                    }}
                    if (token.startsWith('X')) {{
                        const value = parseFloat(token.slice(1));
                        if (!Number.isNaN(value)) {{
                            effects.offsetX = value;
                        }}
                        return;
                    }}
                    if (token.startsWith('Y')) {{
                        const value = parseFloat(token.slice(1));
                        if (!Number.isNaN(value)) {{
                            effects.offsetY = value;
                        }}
                        return;
                    }}
                    if (token.startsWith('V')) {{
                        const value = parseFloat(token.slice(1));
                        if (!Number.isNaN(value) && value > 0) {{
                            effects.vibration = value;
                        }}
                    }}
                }});
            }}

            return {{ name, effects }};
        }}

        function clearVibration(element) {{
            if (element._vibrationAnimation) {{
                element._vibrationAnimation.cancel();
                element._vibrationAnimation = null;
            }}
        }}

        function applyVibration(element, baseTransform, durationSec) {{
            clearVibration(element);
            if (!durationSec || durationSec <= 0) return;

            const jitter = 4;
            const randomOffset = () => Math.round((Math.random() * 2 - 1) * jitter);
            const keyframes = [
                {{ transform: `${{baseTransform}} translate(${{randomOffset()}}px, ${{randomOffset()}}px)` }},
                {{ transform: `${{baseTransform}} translate(${{randomOffset()}}px, ${{randomOffset()}}px)` }},
                {{ transform: `${{baseTransform}} translate(${{randomOffset()}}px, ${{randomOffset()}}px)` }},
                {{ transform: `${{baseTransform}} translate(${{randomOffset()}}px, ${{randomOffset()}}px)` }}
            ];

            element._vibrationAnimation = element.animate(keyframes, {{
                duration: durationSec * 1000,
                iterations: Infinity,
                direction: 'alternate',
                easing: 'linear'
            }});
        }}

        function applyImageEffects(element, effects, baseScale) {{
            const scaleFactor = baseScale * (effects.scale / 100);
            const transform = `translate(${{effects.offsetX}}px, ${{effects.offsetY}}px) scale(${{scaleFactor}})`;
            element.style.filter = effects.monochrome ? 'grayscale(1)' : '';
            element.style.transform = transform;
            applyVibration(element, transform, effects.vibration);
        }}

        function resetImageEffects(element, baseScale) {{
            clearVibration(element);
            element.style.filter = '';
            element.style.transform = `scale(${{baseScale}})`;
        }}

        function normalizeVolume(value) {{
            const volume = Number(value);
            if (Number.isNaN(volume)) return 0;
            return Math.min(Math.max(volume, 0), 1);
        }}

        function clearBgmFade() {{
            if (bgmFadeInterval) {{
                clearInterval(bgmFadeInterval);
                bgmFadeInterval = null;
            }}
        }}

        function getBgmTargetVolume() {{
            return normalizeVolume((gameState.settings.bgmVolume || 0) / 100);
        }}

        function stopBgmImmediately() {{
            clearBgmFade();
            if (bgmAudio) {{
                bgmAudio.pause();
                bgmAudio.currentTime = 0;
                bgmAudio = null;
            }}
            currentBgmName = '';
        }}

        function fadeAudioVolume(audio, fromVolume, toVolume, duration, onComplete) {{
            clearBgmFade();
            const start = performance.now();
            const safeFrom = normalizeVolume(fromVolume);
            const safeTo = normalizeVolume(toVolume);
            audio.volume = safeFrom;

            bgmFadeInterval = setInterval(() => {{
                const elapsed = performance.now() - start;
                const progress = Math.min(elapsed / duration, 1);
                audio.volume = safeFrom + (safeTo - safeFrom) * progress;

                if (progress >= 1) {{
                    clearBgmFade();
                    audio.volume = safeTo;
                    if (onComplete) onComplete();
                }}
            }}, 50);
        }}

        function fadeOutCurrentBgm(onComplete) {{
            if (!bgmAudio) {{
                currentBgmName = '';
                if (onComplete) onComplete();
                return;
            }}

            const audio = bgmAudio;
            fadeAudioVolume(audio, audio.volume, 0, BGM_FADE_DURATION, () => {{
                audio.pause();
                audio.currentTime = 0;
                if (bgmAudio === audio) {{
                    bgmAudio = null;
                }}
                currentBgmName = '';
                if (onComplete) onComplete();
            }});
        }}

        function retryBgmOnNextInteraction(audio, name) {{
            const retry = () => {{
                if (bgmAudio !== audio || currentBgmName !== name) {{
                    return;
                }}
                const playPromise = audio.play();
                if (playPromise && typeof playPromise.catch === 'function') {{
                    playPromise.catch(err => {{
                        console.warn('BGM playback retry was blocked:', err);
                    }});
                }}
            }};

            ['pointerdown', 'keydown', 'touchstart'].forEach(eventName => {{
                document.addEventListener(eventName, retry, {{ once: true }});
            }});
        }}

        function startBgm(name) {{
            const src = AUDIO_ASSETS[name];
            if (!src) {{
                console.warn(`BGM asset not found: ${{name}}`);
                fadeOutCurrentBgm();
                return;
            }}

            const nextAudio = new Audio(src);
            nextAudio.loop = true;
            nextAudio.preload = 'auto';
            nextAudio.volume = 0;

            const playPromise = nextAudio.play();
            if (playPromise && typeof playPromise.catch === 'function') {{
                playPromise.catch(err => {{
                    console.warn('BGM playback was blocked:', err);
                    retryBgmOnNextInteraction(nextAudio, name);
                }});
            }}

            bgmAudio = nextAudio;
            currentBgmName = name;
            fadeAudioVolume(nextAudio, 0, getBgmTargetVolume(), BGM_FADE_DURATION);
        }}

        function getTitleBgmName() {{
            return extractAssetName(CONFIG.adv_title_music);
        }}

        function activateTitleScreen() {{
            showScreen('title-screen');
            updateBgm(getTitleBgmName());
        }}

        function switchToBgm(name) {{
            if (!name) {{
                fadeOutCurrentBgm();
                return;
            }}

            if (currentBgmName === name && bgmAudio) {{
                clearBgmFade();
                bgmAudio.loop = true;
                bgmAudio.volume = getBgmTargetVolume();
                return;
            }}

            fadeOutCurrentBgm(() => startBgm(name));
        }}

        function updateBgm(rawName) {{
            const name = extractAssetName(rawName);
            switchToBgm(name);
        }}
        
        // 背景を更新
        function updateBackground(bgImage) {{
            const bgLayer = document.getElementById('background-layer');
            const parsed = parseImageSpec(bgImage);
            if (parsed.name && ASSETS[parsed.name]) {{
                bgLayer.style.backgroundImage = `url(${{ASSETS[parsed.name]}})`;
                if (parsed.effects) {{
                    applyImageEffects(bgLayer, parsed.effects, BACKGROUND_BASE_SCALE);
                }} else {{
                    resetImageEffects(bgLayer, BACKGROUND_BASE_SCALE);
                }}
            }} else {{
                bgLayer.style.backgroundImage = '';
                resetImageEffects(bgLayer, BACKGROUND_BASE_SCALE);
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
            const parsed = parseImageSpec(imageName);
            if (parsed.name && ASSETS[parsed.name]) {{
                element.style.backgroundImage = `url(${{ASSETS[parsed.name]}})`;
                element.classList.add('visible');
                if (parsed.effects) {{
                    applyImageEffects(element, parsed.effects, CHARACTER_BASE_SCALE);
                }} else {{
                    resetImageEffects(element, CHARACTER_BASE_SCALE);
                }}
            }} else {{
                element.style.backgroundImage = '';
                element.classList.remove('visible');
                resetImageEffects(element, CHARACTER_BASE_SCALE);
            }}
        }}
        
        function clearCharacters() {{
            ['char-left', 'char-center', 'char-right'].forEach(id => {{
                const element = document.getElementById(id);
                element.style.backgroundImage = '';
                element.classList.remove('visible');
                resetImageEffects(element, CHARACTER_BASE_SCALE);
            }});
        }}
        
        // 画面切り替え
        function showScreen(screenId) {{
            document.querySelectorAll('.screen').forEach(screen => {{
                const isTarget = screen.id === screenId;
                screen.classList.toggle('active', isTarget);
                screen.hidden = !isTarget;
            }});
        }}
        
        // セーブ/ロード
        function saveGame() {{
            try {{
                const saved = safeStorageSet(SAVE_DATA_KEY, JSON.stringify({{
                    sceneIndex: currentSceneIndex,
                    state: gameState,
                    history: conversationHistory
                }}));
                if (!saved) {{
                    throw new Error('localStorage に保存できませんでした');
                }}
                alert('セーブしました!');
                closeGameMenu();
            }} catch (e) {{
                alert('セーブに失敗しました: ' + e.message);
            }}
        }}
        
        function loadGame() {{
            if (isLicenseRequired() && !licenseAccepted) {{
                showLicenseModal(true);
                return;
            }}
            try {{
                const saveData = safeStorageGet(SAVE_DATA_KEY);
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

        function getLicenseText() {{
            const raw = (CONFIG.License || CONFIG.license || '');
            if (typeof raw !== 'string') return '';
            return raw.replace(/\\r\\n/g, '\\n').replace(/\\n/g, '\\n').trim();
        }}

        function parseBool(value) {{
            if (typeof value === 'boolean') return value;
            if (value === null || value === undefined) return false;
            const text = String(value).trim().toLowerCase();
            return ['1', 'true', 'yes', 'on'].includes(text);
        }}

        function isCustomNameEnabled() {{
            return parseBool(CONFIG.custom_name || CONFIG.customName);
        }}

        function normalizeCustomName(value) {{
            return String(value || '').replace(/[^\\p{{L}}\\p{{N}}]+/gu, '');
        }}

        const FORBIDDEN_WORDS = (Array.isArray(CONFIG.forbidden_word) ? CONFIG.forbidden_word : [])
            .map(word => normalizeCustomName(word))
            .filter(word => word);

        function validateCustomName(raw) {{
            const normalized = normalizeCustomName(raw);
            if (!normalized) {{
                return {{ ok: false, message: '有効な文字がありません。' }};
            }}
            for (const word of FORBIDDEN_WORDS) {{
                if (word && normalized.includes(word)) {{
                    return {{ ok: false, message: '使用できない単語が含まれています。' }};
                }}
            }}
            return {{ ok: true, value: normalized }};
        }}

        function applyCustomName(text) {{
            const base = String(text || '');
            if (!isCustomNameEnabled()) return base;
            const name = gameState.settings.customName || '';
            return base.replace(/<\\$custom_name\\$>/g, name);
        }}

        function hasCustomName() {{
            return (gameState.settings.customName || '').length > 0;
        }}

        function syncCustomNameInputs(value) {{
            const input = document.getElementById('custom-name-input');
            if (input) input.value = value || '';
            const modalInput = document.getElementById('custom-name-modal-input');
            if (modalInput) modalInput.value = value || '';
        }}

        function showCustomNameError(message) {{
            const errorEl = document.getElementById('custom-name-error');
            if (!errorEl) return;
            if (message) {{
                errorEl.textContent = message;
                errorEl.classList.remove('hidden');
            }} else {{
                errorEl.textContent = '';
                errorEl.classList.add('hidden');
            }}
        }}

        function isLicenseRequired() {{
            return getLicenseText().length > 0;
        }}

        function showLicenseModal(force) {{
            if (!isLicenseRequired()) return;
            if (licenseAccepted && !force) return;
            const modal = document.getElementById('license-modal');
            const textEl = document.getElementById('license-text');
            textEl.textContent = getLicenseText();
            modal.classList.remove('hidden');
        }}

        function acceptLicense() {{
            licenseAccepted = true;
            safeStorageSet(LICENSE_ACCEPT_KEY, 'true');
            document.getElementById('license-modal').classList.add('hidden');
            maybePromptCustomName();
        }}

        function declineLicense() {{
            licenseAccepted = false;
            safeStorageRemove(LICENSE_ACCEPT_KEY);
            alert('ライセンスに同意しないとゲームを開始できません。');
            showLicenseModal(true);
        }}

        function loadLicenseAcceptance() {{
            licenseAccepted = safeStorageGet(LICENSE_ACCEPT_KEY) === 'true';
        }}

        function maybePromptCustomName() {{
            if (!isCustomNameEnabled()) return;
            if (isLicenseRequired() && !licenseAccepted) return;
            if (hasCustomName()) return;
            showCustomNameModal(true);
        }}

        function showCustomNameModal(force) {{
            if (!isCustomNameEnabled()) return;
            const modal = document.getElementById('custom-name-modal');
            if (!modal) return;
            if (modal.classList.contains('hidden') || force) {{
                syncCustomNameInputs(gameState.settings.customName);
                showCustomNameError('');
                modal.classList.remove('hidden');
            }}
        }}

        function hideCustomNameModal() {{
            const modal = document.getElementById('custom-name-modal');
            if (modal) modal.classList.add('hidden');
        }}

        function confirmCustomName() {{
            const input = document.getElementById('custom-name-modal-input');
            const raw = input ? input.value : '';
            const result = validateCustomName(raw);
            if (!result.ok) {{
                showCustomNameError(result.message);
                return;
            }}
            gameState.settings.customName = result.value;
            syncCustomNameInputs(result.value);
            showCustomNameError('');
            saveSettings();
            hideCustomNameModal();
        }}

        function skipCustomName() {{
            hideCustomNameModal();
        }}
        
        // 設定
        function initCustomNameUI() {{
            const setting = document.getElementById('custom-name-setting');
            if (!setting) return;
            if (isCustomNameEnabled()) {{
                setting.classList.remove('hidden');
            }} else {{
                setting.classList.add('hidden');
            }}
        }}

        function loadSettings() {{
            const saved = safeStorageGet(SETTINGS_KEY);
            if (saved) {{
                try {{
                    const parsed = JSON.parse(saved);
                    gameState.settings = {{ ...DEFAULT_SETTINGS, ...parsed }};
                }} catch (e) {{
                    console.warn('設定の読み込みに失敗しました:', e);
                    gameState.settings = {{ ...DEFAULT_SETTINGS }};
                }}
            }} else {{
                gameState.settings = {{ ...DEFAULT_SETTINGS }};
            }}
            document.getElementById('text-speed').value = gameState.settings.textSpeed;
            document.getElementById('bgm-volume').value = gameState.settings.bgmVolume;
            document.getElementById('se-volume').value = gameState.settings.seVolume;
            syncCustomNameInputs(gameState.settings.customName);
            if (bgmAudio) {{
                bgmAudio.volume = getBgmTargetVolume();
            }}
        }}
        
        function saveSettings() {{
            gameState.settings.textSpeed = parseInt(document.getElementById('text-speed').value);
            gameState.settings.bgmVolume = parseInt(document.getElementById('bgm-volume').value);
            gameState.settings.seVolume = parseInt(document.getElementById('se-volume').value);
            if (isCustomNameEnabled()) {{
                const input = document.getElementById('custom-name-input');
                const raw = input ? input.value : '';
                const trimmed = String(raw || '').trim();
                if (!trimmed) {{
                    gameState.settings.customName = '';
                }} else {{
                    const result = validateCustomName(raw);
                    if (!result.ok) {{
                        alert(result.message);
                        return false;
                    }}
                    gameState.settings.customName = result.value;
                    syncCustomNameInputs(result.value);
                }}
            }}
            if (bgmAudio) {{
                bgmAudio.volume = getBgmTargetVolume();
            }}
            safeStorageSet(SETTINGS_KEY, JSON.stringify(gameState.settings));
            return true;
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
            if (!saveSettings()) return;
            document.getElementById('settings-screen').classList.add('hidden');
        }}
        
        function showCredits() {{
            document.getElementById('credits-screen').classList.remove('hidden');
        }}
        
        function closeCredits() {{
            document.getElementById('credits-screen').classList.add('hidden');
        }}
        
        function returnToTitle() {{
            activateTitleScreen();
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
        csv_base_name = Path(csv_file).stem
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        output_filename = f"{csv_base_name}{timestamp}.html"
        generator.generate_html(output_filename, latest_filename="game.html")
        
        print()
        print("=" * 60)
        print("  ✓ 生成完了!")
        print("=" * 60)
        print()
        print(f"生成されたファイル: {output_dir}/{output_filename}")
        print(f"最新版: {output_dir}/game.html")
        print("ブラウザで開いてゲームをお楽しみください!")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

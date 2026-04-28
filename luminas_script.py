#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LuminasScript - Visual Novel Game Generator
CSVファイルからビジュアルノベル形式のウェブゲームを生成します。
"""

import argparse
import csv
import base64
import hashlib
import json
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class LuminasScript:
    """CSVからビジュアルノベルゲームを生成するメインクラス"""

    DEPRECATED_CHOICE_JUMP_PATTERN = re.compile(r'(?i)\bJUMP_([ABCD])\s*\(\s*([^()\s,;|<>]+)\s*\)')

    IMAGE_EXTENSION_MIME_MAP = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    AUDIO_EXTENSION_MIME_MAP = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4'
    }
    FAVICON_EXTENSION_MIME_MAP = {
        '.ico': 'image/x-icon',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml'
    }
    OBFUSCATION_HEADER_SIZE = 16
    OBFUSCATED_ASSET_EXTENSION = '.bin'
    LOCAL_ASSET_SCRIPT_DIRNAME = '_local'

    STANDING_PORTRAIT_FIELDS = (
        'center_standing_portrait_image',
        'left_standing_portrait_image',
        'right_standing_portrait_image'
    )
    GLOBAL_STANDING_PORTRAIT_CONFIG_MAP = {
        'center_standing_portrait_image': 'custom_all_center_standing_portrait_image',
        'left_standing_portrait_image': 'custom_all_left_standing_portrait_image',
        'right_standing_portrait_image': 'custom_all_right_standing_portrait_image'
    }
    
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
            'AUTO_SCENE_CHANGE_DELAY_def': '3000',
            'CLICK_DELAY_def': '500',
            'creator_name': '',
            'License': '',
            'custom_name': '',
            'custom_all_center_standing_portrait_image': '',
            'custom_all_left_standing_portrait_image': '',
            'custom_all_right_standing_portrait_image': '',
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
                        self._apply_global_standing_portrait_customizations()
                        print(f"✓ {len(self.scenario_data)}行のシナリオデータを読み込みました (encoding: {encoding})")
                        return
                    
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"⚠ エンコーディング {encoding} で読み込み失敗: {e}")
                continue
        
        raise ValueError(f"CSVファイルのエンコーディングを検出できませんでした: {csv_path}")
    
    def _build_image_payload(self, image_path: Path) -> Optional[Tuple[bytes, str]]:
        """画像ファイルを出力用のバイト列へ変換"""
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

            return payload, mime_type
        except Exception as e:
            print(f"⚠ 画像の処理に失敗: {image_path} - {e}")
            return None

    def _build_audio_payload(self, audio_path: Path) -> Optional[Tuple[bytes, str]]:
        """音声ファイルを出力用のバイト列へ変換"""
        if not audio_path.exists():
            print(f"⚠ 音声が見つかりません: {audio_path}")
            return None

        try:
            with open(audio_path, 'rb') as f:
                payload = f.read()

            ext = audio_path.suffix.lower()
            mime_type = self.AUDIO_EXTENSION_MIME_MAP.get(ext, 'application/octet-stream')
            return payload, mime_type
        except Exception as e:
            print(f"⚠ 音声の処理に失敗: {audio_path} - {e}")
            return None

    def _read_file_payload(self, file_path: Path, mime_type: str) -> Optional[Tuple[bytes, str]]:
        """任意ファイルをそのまま読み込む"""
        if not file_path.exists():
            print(f"⚠ ファイルが見つかりません: {file_path}")
            return None

        try:
            with open(file_path, 'rb') as f:
                payload = f.read()
            return payload, mime_type
        except Exception as e:
            print(f"⚠ ファイルの読み込みに失敗: {file_path} - {e}")
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

    def _obfuscate_asset_payload(self, payload: bytes) -> Tuple[bytes, int]:
        """先頭バイトを入れ替えて難読化する"""
        if not payload:
            return payload, 0

        header_size = min(self.OBFUSCATION_HEADER_SIZE, len(payload))
        header = payload[:header_size][::-1]
        return header + payload[header_size:], header_size

    def _build_obfuscated_asset_meta(
        self,
        asset_category: str,
        logical_name: str,
        payload: bytes,
        mime_type: str
    ) -> Tuple[Dict[str, object], bytes]:
        """難読化済みアセットのメタ情報とペイロードを組み立てる"""
        digest_source = f"{asset_category}:{logical_name}:{mime_type}".encode('utf-8') + payload
        hashed_name = hashlib.sha256(digest_source).hexdigest()
        output_name = f"{hashed_name}{self.OBFUSCATED_ASSET_EXTENSION}"

        obfuscated_payload, header_swap_size = self._obfuscate_asset_payload(payload)
        meta = {
            'path': f"assets/{output_name}",
            'mimeType': mime_type,
            'headerSwapSize': header_swap_size
        }
        return meta, obfuscated_payload

    def _write_obfuscated_asset(
        self,
        output_assets_dir: Optional[Path],
        asset_category: str,
        logical_name: str,
        payload: bytes,
        mime_type: str,
        write_asset_file: bool = True
    ) -> Tuple[Dict[str, object], str]:
        """難読化済みアセットのメタ情報を返し、必要ならファイルも書き出す"""
        meta, obfuscated_payload = self._build_obfuscated_asset_meta(
            asset_category,
            logical_name,
            payload,
            mime_type
        )

        if write_asset_file:
            if output_assets_dir is None:
                raise ValueError("アセット出力先が指定されていません")
            output_path = output_assets_dir / Path(meta['path']).name
            with open(output_path, 'wb') as f:
                f.write(obfuscated_payload)

        payload_b64 = base64.b64encode(obfuscated_payload).decode('ascii')
        return meta, payload_b64

    def _register_file_asset(
        self,
        output_assets_dir: Optional[Path],
        asset_category: str,
        logical_name: str,
        source_path: Path,
        asset_type: str,
        write_asset_file: bool = True
    ) -> Optional[Tuple[Dict[str, object], str]]:
        """画像・音声・その他ファイルを出力アセットとして登録"""
        if asset_type == 'image':
            built = self._build_image_payload(source_path)
        elif asset_type == 'audio':
            built = self._build_audio_payload(source_path)
        else:
            mime_type = self.FAVICON_EXTENSION_MIME_MAP.get(source_path.suffix.lower(), 'application/octet-stream')
            built = self._read_file_payload(source_path, mime_type)

        if not built:
            return None

        payload, mime_type = built
        return self._write_obfuscated_asset(
            output_assets_dir,
            asset_category,
            logical_name,
            payload,
            mime_type,
            write_asset_file=write_asset_file
        )

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

    def _normalize_effect_token(self, token: str) -> str:
        """全角ハイフン類を半角ハイフンへ正規化"""
        return str(token).replace('‐', '-').replace('‑', '-').replace('‒', '-').replace('–', '-').replace('—', '-').replace('−', '-')

    def _looks_like_effects_only_spec(self, spec: str) -> bool:
        """ファイル名なしのエフェクト指定か判定"""
        text = str(spec or '').strip()
        if not text:
            return False

        tokens = [self._normalize_effect_token(token.strip()) for token in text.split(',') if token.strip()]
        if not tokens:
            return False

        for token in tokens:
            upper = token.upper()
            if upper == 'M':
                continue
            if upper.startswith(('S', 'X', 'Y', 'V')):
                try:
                    float(token[1:])
                except ValueError:
                    return False
                continue
            return False

        return True

    def _parse_image_spec(self, spec: str) -> Dict[str, Optional[Dict[str, float]]]:
        """画像指定を {name, effects} へ分解"""
        text = str(spec or '').strip()
        if not text:
            return {'name': '', 'effects': None}

        if self._looks_like_effects_only_spec(text):
            text = f"<|{text}>"
        elif not (text.startswith('<') and text.endswith('>')):
            return {'name': text, 'effects': None}

        inner = text[1:-1].strip()
        if not inner:
            return {'name': '', 'effects': None}

        name_part, effect_part = (inner.split('|', 1) + [''])[:2]
        name = name_part.strip()
        if not effect_part.strip():
            return {'name': name, 'effects': None}

        effects = {
            'monochrome': False,
            'scale': 100.0,
            'offsetX': 0.0,
            'offsetY': 0.0,
            'vibration': 0.0
        }

        tokens = [self._normalize_effect_token(token.strip()) for token in effect_part.split(',') if token.strip()]
        for token in tokens:
            upper = token.upper()
            if upper == 'M':
                effects['monochrome'] = True
                continue
            if upper.startswith('S'):
                try:
                    value = float(token[1:])
                except ValueError:
                    continue
                if value > 0:
                    effects['scale'] = value
                continue
            if upper.startswith('X'):
                try:
                    effects['offsetX'] = float(token[1:])
                except ValueError:
                    pass
                continue
            if upper.startswith('Y'):
                try:
                    effects['offsetY'] = float(token[1:])
                except ValueError:
                    pass
                continue
            if upper.startswith('V'):
                try:
                    value = float(token[1:])
                except ValueError:
                    continue
                if value > 0:
                    effects['vibration'] = value

        return {'name': name, 'effects': effects}

    def _has_image_effects(self, effects: Optional[Dict[str, float]]) -> bool:
        """エフェクト指定があるか判定"""
        if not effects:
            return False
        return (
            bool(effects.get('monochrome')) or
            float(effects.get('scale', 100)) != 100 or
            float(effects.get('offsetX', 0)) != 0 or
            float(effects.get('offsetY', 0)) != 0 or
            float(effects.get('vibration', 0)) != 0
        )

    def _format_image_effect_value(self, value: float) -> str:
        """数値エフェクトをCSV記法へ戻す"""
        return str(int(value)) if float(value).is_integer() else f"{value:g}"

    def _compose_image_spec(self, name: str, effects: Optional[Dict[str, float]]) -> str:
        """画像指定をCSV互換の記法へ組み立て"""
        clean_name = str(name or '').strip()
        if not self._has_image_effects(effects):
            return clean_name

        tokens = []
        if effects.get('monochrome'):
            tokens.append('M')
        scale = float(effects.get('scale', 100))
        offset_x = float(effects.get('offsetX', 0))
        offset_y = float(effects.get('offsetY', 0))
        vibration = float(effects.get('vibration', 0))

        if scale != 100:
            tokens.append(f"S{self._format_image_effect_value(scale)}")
        if offset_x != 0:
            tokens.append(f"X{self._format_image_effect_value(offset_x)}")
        if offset_y != 0:
            tokens.append(f"Y{self._format_image_effect_value(offset_y)}")
        if vibration != 0:
            tokens.append(f"V{self._format_image_effect_value(vibration)}")

        return f"<{clean_name}|{','.join(tokens)}>"

    def _merge_image_specs(self, base_spec: str, override_spec: str) -> str:
        """画像指定を重ね掛けで合成"""
        base = self._parse_image_spec(base_spec)
        override = self._parse_image_spec(override_spec)

        name = override['name'] or base['name']
        base_effects = base['effects']
        override_effects = override['effects']

        if not self._has_image_effects(base_effects) and not self._has_image_effects(override_effects):
            return name

        merged = {
            'monochrome': bool(base_effects and base_effects.get('monochrome')) or bool(override_effects and override_effects.get('monochrome')),
            'scale': float(base_effects['scale']) if base_effects else 100.0,
            'offsetX': float(base_effects['offsetX']) if base_effects else 0.0,
            'offsetY': float(base_effects['offsetY']) if base_effects else 0.0,
            'vibration': float(base_effects['vibration']) if base_effects else 0.0
        }

        if override_effects:
            merged['scale'] = merged['scale'] * (float(override_effects['scale']) / 100.0)
            merged['offsetX'] += float(override_effects['offsetX'])
            merged['offsetY'] += float(override_effects['offsetY'])
            merged['vibration'] += float(override_effects['vibration'])

        return self._compose_image_spec(name, merged)

    def _apply_global_standing_portrait_customizations(self) -> None:
        """config.ymlの立ち絵一括指定を各行へ反映"""
        if not self.scenario_data:
            return

        applied_rows = []
        for row in self.scenario_data:
            next_row = dict(row)
            for field, config_key in self.GLOBAL_STANDING_PORTRAIT_CONFIG_MAP.items():
                global_spec = self.config.get(config_key, '')
                if global_spec:
                    next_row[field] = self._merge_image_specs(global_spec, row.get(field, ''))
            applied_rows.append(next_row)

        self.scenario_data = applied_rows

    def collect_assets(
        self,
        output_assets_dir: Optional[Path] = None,
        write_asset_files: bool = True,
        write_local_scripts: bool = True
    ) -> Dict[str, object]:
        """使用アセットを収集し、必要に応じて難読化済みファイルを書き出す"""
        image_assets: Dict[str, Dict[str, object]] = {}
        audio_assets: Dict[str, Dict[str, object]] = {}

        if write_asset_files and output_assets_dir is None:
            raise ValueError("アセットファイルを書き出すには出力先が必要です")
        if write_local_scripts and output_assets_dir is None:
            raise ValueError("ローカルアセットスクリプトを書き出すには出力先が必要です")

        if write_local_scripts and output_assets_dir is not None:
            local_scripts_dir = output_assets_dir / self.LOCAL_ASSET_SCRIPT_DIRNAME
            local_scripts_dir.mkdir(parents=True, exist_ok=True)

        def register_image(directory: Path, asset_name: str, category: str) -> None:
            if not asset_name or asset_name in image_assets or not directory.exists():
                return
            asset_path = self._find_asset_path(directory, asset_name, ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
            if not asset_path:
                return
            registered = self._register_file_asset(
                output_assets_dir,
                category,
                asset_name,
                asset_path,
                'image',
                write_asset_file=write_asset_files
            )
            if registered:
                meta, payload_b64 = registered
                if write_local_scripts and output_assets_dir is not None:
                    self._write_local_asset_script(output_assets_dir, meta['path'], payload_b64)
                image_assets[asset_name] = meta

        def register_audio(directory: Path, asset_name: str, category: str) -> None:
            if not asset_name or asset_name in audio_assets or not directory.exists():
                return
            asset_path = self._find_asset_path(directory, asset_name, ['.mp3', '.wav', '.ogg', '.m4a'])
            if not asset_path:
                return
            registered = self._register_file_asset(
                output_assets_dir,
                category,
                asset_name,
                asset_path,
                'audio',
                write_asset_file=write_asset_files
            )
            if registered:
                meta, payload_b64 = registered
                if write_local_scripts and output_assets_dir is not None:
                    self._write_local_asset_script(output_assets_dir, meta['path'], payload_b64)
                audio_assets[asset_name] = meta

        bg_dir = self.assets_dir / "backgrounds"
        if bg_dir.exists():
            for row in self.scenario_data:
                register_image(bg_dir, self._extract_asset_name(row.get('background_image', '').strip()), 'background')
            register_image(bg_dir, self._extract_asset_name(str(self.config.get('title_bg_image', '')).strip()), 'background')

        char_dir = self.assets_dir / "characters"
        if char_dir.exists():
            for row in self.scenario_data:
                for pos in self.STANDING_PORTRAIT_FIELDS:
                    register_image(char_dir, self._extract_asset_name(row.get(pos, '').strip()), 'character')

        effect_dir = self.assets_dir / "effect"
        if effect_dir.exists():
            for row in self.scenario_data:
                register_image(effect_dir, self._extract_asset_name(row.get('effect', '').strip()), 'effect')

        bgm_dir = self.assets_dir / "bgms"
        if bgm_dir.exists():
            for row in self.scenario_data:
                register_audio(bgm_dir, self._extract_asset_name(row.get('bgm', '').strip()), 'bgm')
            register_audio(bgm_dir, self._extract_asset_name(str(self.config.get('adv_title_music', '')).strip()), 'bgm')

        favicon = self._resolve_favicon_asset(output_assets_dir, write_asset_file=write_asset_files)
        if favicon and favicon.get('path') and favicon.get('payloadBase64'):
            if write_local_scripts and output_assets_dir is not None:
                self._write_local_asset_script(output_assets_dir, favicon['path'], favicon['payloadBase64'])
            favicon = {k: v for k, v in favicon.items() if k != 'payloadBase64'}

        if write_asset_files:
            print(f"✓ 画像{len(image_assets)}個 / 音声{len(audio_assets)}個のアセットを書き出しました")
        else:
            print(f"✓ 画像{len(image_assets)}個 / 音声{len(audio_assets)}個のアセット情報を作成しました")
        return {
            'images': image_assets,
            'audio': audio_assets,
            'favicon': favicon
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

    def _resolve_favicon_asset(
        self,
        output_assets_dir: Optional[Path],
        write_asset_file: bool = True
    ) -> Dict[str, object]:
        """favicon_urlを出力アセットへ解決"""
        raw = str(self.config.get('favicon_url') or '').strip()
        if not raw:
            return {}

        lowered = raw.lower()
        if lowered.startswith(('data:', 'http://', 'https://')):
            return {'href': raw}

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
            return {}

        registered = self._register_file_asset(
            output_assets_dir,
            'favicon',
            raw,
            favicon_path,
            'file',
            write_asset_file=write_asset_file
        )
        if not registered:
            return {}

        meta, payload_b64 = registered
        meta['payloadBase64'] = payload_b64
        return meta

    def _write_local_asset_script(self, output_assets_dir: Path, asset_path: str, payload_b64: str) -> None:
        """file:// 直開き用に単一アセットの復元スクリプトを書き出す"""
        asset_name = Path(asset_path).name
        script_path = output_assets_dir / self.LOCAL_ASSET_SCRIPT_DIRNAME / f"{asset_name}.js"
        script = (
            "window.__LUMINA_LOCAL_ASSET_PACK__ = window.__LUMINA_LOCAL_ASSET_PACK__ || {};\n"
            f"window.__LUMINA_LOCAL_ASSET_PACK__[{json.dumps(asset_path, ensure_ascii=False)}] = "
            f"{json.dumps(payload_b64, ensure_ascii=False)};\n"
        )
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
    
    def _build_html_content(
        self,
        output_assets_dir: Optional[Path],
        write_asset_files: bool,
        write_local_scripts: bool
    ) -> str:
        """HTML文字列を組み立てる"""
        assets = self.collect_assets(
            output_assets_dir=output_assets_dir,
            write_asset_files=write_asset_files,
            write_local_scripts=write_local_scripts
        )
        self._log_deprecated_choice_jumps()
        scenario_json = json.dumps(self.scenario_data, ensure_ascii=False, indent=2)
        image_assets_json = json.dumps(assets['images'], ensure_ascii=False)
        audio_assets_json = json.dumps(assets['audio'], ensure_ascii=False)
        favicon_asset_json = json.dumps(assets['favicon'], ensure_ascii=False)
        config_json = json.dumps(self.config, ensure_ascii=False)

        return self._generate_html_template(
            scenario_json,
            image_assets_json,
            audio_assets_json,
            favicon_asset_json,
            config_json
        )

    def generate_html(self, csv_filename: str = "scenario.csv") -> Path:
        """HTMLとassetsディレクトリを生成し、出力ディレクトリを返す"""
        if not self.scenario_data:
            raise ValueError("シナリオデータが読み込まれていません")

        csv_base_name = Path(csv_filename).stem
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        bundle_dir = self.output_dir / f"{csv_base_name}_{timestamp}"
        assets_output_dir = bundle_dir / "assets"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        bundle_dir.mkdir(parents=True, exist_ok=False)
        assets_output_dir.mkdir(parents=True, exist_ok=False)

        html_content = self._build_html_content(
            output_assets_dir=assets_output_dir,
            write_asset_files=True,
            write_local_scripts=True
        )

        output_path = bundle_dir / "game.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✓ ゲームファイルを生成しました: {output_path}")
        print(f"  ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")

        return bundle_dir

    def generate_replacement_html(self, csv_filename: str = "scenario.csv") -> Path:
        """差し替え用にHTMLのみをoutput直下へ出力する"""
        if not self.scenario_data:
            raise ValueError("シナリオデータが読み込まれていません")

        csv_base_name = Path(csv_filename).stem
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = self.output_dir / f"{csv_base_name}_{timestamp}.html"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        html_content = self._build_html_content(
            output_assets_dir=None,
            write_asset_files=False,
            write_local_scripts=False
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✓ 差し替え用HTMLを生成しました: {output_path}")
        print(f"  ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")

        return output_path

    def _normalize_scene_id(self, scene_id: Optional[str]) -> str:
        """scene_idを比較用に正規化"""
        return str(scene_id or '').strip()

    def _is_choice_scene_id(self, scene_id: Optional[str]) -> bool:
        """scene_idが選択肢ページかどうか"""
        parts = self._normalize_scene_id(scene_id).split('-')
        if len(parts) < 2:
            return False
        last = parts[-1]
        second = parts[1]
        return last == 'Q' or second == 'Q'

    def _extract_deprecated_choice_jumps(self, script: Optional[str]) -> List[Tuple[str, str]]:
        """script列からJUMP_A/B/C/D指定を抽出"""
        if not script:
            return []
        return [
            (branch.upper(), self._normalize_scene_id(target))
            for branch, target in self.DEPRECATED_CHOICE_JUMP_PATTERN.findall(str(script))
            if self._normalize_scene_id(target)
        ]

    def _log_deprecated_choice_jumps(self) -> None:
        """非推奨のJUMP_A/B/C/D使用箇所を生成ログへ出力"""
        for scene in self.scenario_data:
            scene_id = self._normalize_scene_id(scene.get('scene_id'))
            jumps = self._extract_deprecated_choice_jumps(scene.get('script'))
            if not jumps:
                continue

            if not self._is_choice_scene_id(scene_id):
                for branch, target in jumps:
                    print(
                        f"⚠ 非推奨のJUMP_{branch}を検出しましたが、このscene_idでは無効です: "
                        f"{scene_id or '(scene_idなし)'} -> {target}"
                    )
                continue

            for branch, target in jumps:
                print(
                    f"⚠ 非推奨のJUMP_{branch}を検出: "
                    f"scene_id={scene_id} から 選択肢{branch} のジャンプ先として {target} を使用"
                )
    
    def _generate_html_template(
        self,
        scenario_json: str,
        image_assets_json: str,
        audio_assets_json: str,
        favicon_asset_json: str,
        config_json: str
    ) -> str:
        """HTMLテンプレートを生成"""
        default_volume = self._parse_volume(self.config.get('music_def_volume'))
        show_title_text = not self._parse_bool(self.config.get('adv_text_title_off'))
        font_import = ""
        if self.config.get('text_font_importURL'):
            font_import = f'<link href="{self.config["text_font_importURL"]}" rel="stylesheet">'

        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.get('adv_title', 'LuminasScript Game')}</title>
    {font_import}
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <!-- ローディング画面 -->
    <div id="loading-screen">
        <div class="loading-frame">
            <div class="loading-content">
                <div class="spinner"></div>
                <p class="loading-text">ロードしてます...</p>
                <div class="loading-meta">
                    <p id="loading-image-count">画像: 0 / 0</p>
                    <p id="loading-audio-count">音声: 0 / 0</p>
                </div>
            </div>
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
            <button id="title-fullscreen-button" class="fullscreen-button" onclick="toggleFullscreen()" title="最大化" aria-label="最大化">
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
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

            <div id="effect-layer" class="layer effect-overlay"></div>
            
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
                    <button id="fullscreen-button" class="fullscreen-button" onclick="toggleFullscreen()" title="最大化" aria-label="最大化">
                        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                    <button id="history-button" onclick="toggleHistory()" title="会話履歴" aria-label="会話履歴">
                        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path d="M2.5 5.75C2.5 4.78 3.28 4 4.25 4h5.25c1.18 0 2.3.34 3.25.95.95-.61 2.07-.95 3.25-.95h5.25c.97 0 1.75.78 1.75 1.75v11.5c0 .41-.34.75-.75.75h-5.63c-1.15 0-2.26.34-3.21.97a.75.75 0 0 1-.83 0A5.78 5.78 0 0 0 9.5 18H3.25a.75.75 0 0 1-.75-.75V5.75Zm9.75.03v10.99A7.26 7.26 0 0 0 9.5 16H4V5.78h5.5c1 0 1.96.27 2.75.78Zm1.5 10.99A7.26 7.26 0 0 1 16.5 16H22V5.78h-5.5c-1 0-1.96.27-2.75.78v10.21Z" fill="currentColor"/>
                        </svg>
                    </button>
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
                <div id="history-help-text" class="history-help-text"></div>
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

        <!-- セーブ/ロード画面 -->
        <div id="save-load-screen" class="modal hidden">
            <div class="modal-content save-load-content">
                <h2 id="save-load-title">ロード</h2>
                <p id="save-load-summary" class="save-load-summary"></p>
                <div id="save-load-tools" class="save-load-tools hidden">
                    <button class="slot-action-btn" onclick="exportSaveBackup()">バックアップ出力</button>
                    <button class="slot-action-btn" onclick="promptImportSaveBackup()">インポート</button>
                    <input type="file" id="save-backup-input" accept=".json,application/json" class="hidden" onchange="importSaveBackupFromFile(event)">
                </div>
                <div id="save-slot-list" class="save-slot-list"></div>
                <button class="menu-btn" onclick="closeSaveLoadModal()">閉じる</button>
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
                <div class="setting-item">
                    <label>オート送り速度</label>
                    <input type="range" id="auto-scene-change-delay" min="500" max="10000" step="100" value="3000">
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

        <!-- NOTICE ポップアップ -->
        <div id="notice-modal" class="modal hidden">
            <div class="modal-content notice-content" onclick="event.stopPropagation()">
                <h2>お知らせ</h2>
                <div id="notice-text" class="notice-text"></div>
                <div class="license-actions">
                    <button class="menu-btn" onclick="closeNoticeModal()">分かった</button>
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
        {self._get_javascript(scenario_json, image_assets_json, audio_assets_json, favicon_asset_json, config_json)}
    </script>
</body>
</html>"""
    
    def _get_css(self) -> str:
        """CSSスタイルを返す"""
        theme_color = self.config.get('theme_color', '#667EEA')
        sub_color = self.config.get('sub_color', '#754CA3')
        text_color = self.config.get('text_color', '#FFFFFF')
        
        return f"""
        :root {{
            --lumina-frame-width: min(100vw, calc(100vh * (16 / 9)));
            --lumina-frame-height: min(100vh, calc(100vw * (9 / 16)));
        }}

        @supports (height: 100dvh) {{
            :root {{
                --lumina-frame-width: min(100vw, calc(100dvh * (16 / 9)));
                --lumina-frame-height: min(100dvh, calc(100vw * (9 / 16)));
            }}
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html {{
            width: 100%;
            height: 100%;
        }}

        .hidden {{
            display: none !important;
        }}
        
        body {{
            width: 100%;
            height: 100%;
            min-height: 100vh;
            min-height: 100dvh;
            font-family: 'Kosugi Maru', 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
            overflow: hidden;
            background: #000;
            color: {text_color};
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        /* ローディング画面 */
        #loading-screen {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            background: #000;
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

        .loading-frame {{
            width: var(--lumina-frame-width);
            height: var(--lumina-frame-height);
            aspect-ratio: 16 / 9;
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
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

        .loading-meta {{
            margin-top: 1rem;
            font-size: 1rem;
            line-height: 1.8;
            opacity: 0.92;
            font-variant-numeric: tabular-nums;
        }}
        
        #game-container {{
            width: var(--lumina-frame-width);
            height: var(--lumina-frame-height);
            aspect-ratio: 16 / 9;
            position: relative;
            overflow: hidden;
            flex: 0 0 auto;
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
            right: 5rem;
            bottom: 1rem;
            color: rgba(255, 255, 255, 0.45);
            font-size: 0.9rem;
            letter-spacing: 0.08em;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
            pointer-events: none;
        }}

        #title-fullscreen-button {{
            position: absolute;
            right: 1rem;
            bottom: 1rem;
            z-index: 2;
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

        #effect-layer {{
            background-size: contain;
            background-position: center;
            background-repeat: no-repeat;
            pointer-events: none;
            z-index: 2;
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
            z-index: 3;
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

        #text-box.text-back-off {{
            background: transparent;
            box-shadow: none;
        }}
        
        #speaker-name {{
            font-size: 1.3rem;
            font-weight: bold;
            margin-bottom: 0.8rem;
            color: #ffd700;
        }}
        
        #dialogue-text {{
            font-size: 1.2rem;
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

        #click-gauge-container.text-back-off,
        #click-gauge.text-back-off {{
            display: none;
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
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}

        #title-fullscreen-button,
        #control-buttons .fullscreen-button {{
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: 2px solid white;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            font-size: 1.2rem;
            cursor: pointer;
            transition: background 0.3s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}

        #title-fullscreen-button svg,
        #control-buttons button svg {{
            width: 1.2rem;
            height: 1.2rem;
            display: block;
        }}
        
        #title-fullscreen-button:hover,
        #control-buttons button:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .fullscreen-button.active {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .fullscreen-button.hidden {{
            display: none;
        }}
        
        #auto-button.active {{
            background: linear-gradient(135deg, {theme_color} 0%, {sub_color} 100%);
            border-color: {theme_color};
        }}
        
        /* モーダル */
        .modal {{
            position: absolute;
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
            width: min(92%, 600px);
            min-width: min(400px, 92%);
            max-width: 600px;
            max-height: 80%;
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

        .notice-content {{
            max-width: 560px;
        }}

        .notice-text {{
            background: rgba(0, 0, 0, 0.25);
            padding: 1.2rem;
            border-radius: 10px;
            line-height: 1.8;
            white-space: pre-wrap;
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

        .save-load-content {{
            max-width: 920px;
            width: min(92%, 920px);
        }}

        .save-load-summary {{
            margin-bottom: 1rem;
            text-align: center;
            opacity: 0.85;
        }}

        .save-load-tools {{
            display: flex;
            gap: 0.8rem;
            justify-content: center;
            margin-bottom: 1rem;
        }}

        .save-slot-list {{
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
            max-height: 40vh;
            overflow-y: auto;
            margin-bottom: 1.5rem;
        }}

        .save-slot-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 1.2rem;
            border-radius: 10px;
            background: rgba(0, 0, 0, 0.28);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }}

        .save-slot-item.empty {{
            opacity: 0.9;
        }}

        .save-slot-meta {{
            flex: 1;
            min-width: 0;
        }}

        .save-slot-header {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            align-items: baseline;
            margin-bottom: 0.3rem;
        }}

        .save-slot-number {{
            font-size: 1.1rem;
            font-weight: bold;
        }}

        .save-slot-time {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}

        .save-slot-scene,
        .save-slot-preview {{
            overflow-wrap: anywhere;
            line-height: 1.5;
        }}

        .save-slot-preview {{
            font-size: 0.95rem;
            opacity: 0.95;
        }}

        .save-slot-empty {{
            opacity: 0.75;
        }}

        .save-slot-actions {{
            display: flex;
            gap: 0.6rem;
            flex-shrink: 0;
        }}

        .slot-action-btn {{
            border: 1px solid rgba(255, 255, 255, 0.45);
            background: rgba(255, 255, 255, 0.14);
            color: white;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            min-width: 6.5rem;
            transition: background 0.2s, transform 0.2s;
        }}

        .slot-action-btn:hover:not(:disabled) {{
            background: rgba(255, 255, 255, 0.22);
            transform: translateY(-1px);
        }}

        .slot-action-btn:disabled {{
            opacity: 0.45;
            cursor: not-allowed;
        }}

        .slot-action-btn.danger {{
            background: rgba(160, 32, 32, 0.35);
        }}

        .slot-action-btn.danger:hover:not(:disabled) {{
            background: rgba(180, 32, 32, 0.48);
        }}
        
        #history-list {{
            background: rgba(0, 0, 0, 0.3);
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            max-height: 60vh;
            overflow-y: auto;
        }}

        .history-help-text {{
            margin-bottom: 1rem;
            text-align: center;
            font-size: 0.95rem;
            opacity: 0.85;
        }}
        
        .history-item {{
            margin-bottom: 1.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            transition: background 0.2s, border-color 0.2s, transform 0.2s, opacity 0.2s;
        }}

        .history-item.jumpable {{
            cursor: pointer;
        }}

        .history-item.jumpable:hover,
        .history-item.jumpable:focus {{
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.45);
            transform: translateY(-1px);
            outline: none;
        }}

        .history-item.locked {{
            opacity: 0.5;
        }}

        .history-item.current {{
            border-left: 3px solid rgba(255, 215, 0, 0.8);
            padding-left: 1rem;
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
            padding: 1rem 6rem;
            font-size: 1.1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            white-space: nowrap;
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

        @media (max-width: 720px) {{
            .save-load-tools {{
                flex-direction: column;
            }}

            .save-slot-item {{
                flex-direction: column;
                align-items: stretch;
            }}

            .save-slot-actions {{
                width: 100%;
            }}

            .slot-action-btn {{
                flex: 1;
            }}
        }}
        """
    
    def _get_javascript(
        self,
        scenario_json: str,
        image_assets_json: str,
        audio_assets_json: str,
        favicon_asset_json: str,
        config_json: str
    ) -> str:
        """JavaScriptコードを返す"""
        default_volume = self._parse_volume(self.config.get('music_def_volume'))
        return f"""
        // ゲームデータ
        const SCENARIO_DATA = {scenario_json};
        const ASSETS = {image_assets_json};
        const AUDIO_ASSETS = {audio_assets_json};
        const FAVICON_ASSET = {favicon_asset_json};
        const CONFIG = {config_json};
        const AUTO_SCENE_CHANGE_DELAY = parsePositiveInt(
            CONFIG.AUTO_SCENE_CHANGE_DELAY_def ?? CONFIG.auto_scene_change_delay_def,
            3000
        );
        const CLICK_DELAY = parsePositiveInt(
            CONFIG.CLICK_DELAY_def ?? CONFIG.click_delay_def,
            500
        );
        const DEFAULT_SETTINGS = {{
            textSpeed: 5,
            autoSceneChangeDelay: AUTO_SCENE_CHANGE_DELAY,
            bgmVolume: {default_volume},
            seVolume: {default_volume},
            customName: ''
        }};
        const BGM_FADE_DURATION = 1000;
        const STORAGE_PREFIX = normalizeStoragePrefix(
            CONFIG.localstorage_prefix ?? CONFIG.localStoragePrefix
        );
        const LEGACY_SAVE_DATA_KEY = getStorageKey('luminas_save');
        const SAVE_SLOT_KEY_PREFIX = getStorageKey('luminas_save_');
        const SAVE_SLOT_COUNT = 99;
        const SETTINGS_KEY = getStorageKey('luminas_settings');
        const STATE_STORE_KEY = getStorageKey('luminas_state_store');
        
        // ゲーム状態
        let currentSceneIndex = 0;
        let conversationHistory = [];
        let sceneNavigationHistory = [];
        let isAutoMode = false;
        let autoModeTimeout = null;
        let clickDelayTimer = null;
        let canClick = false;
        let licenseAccepted = false;
        const LICENSE_ACCEPT_KEY = getStorageKey('luminas_license_accepted');
        let bgmAudio = null;
        let bgmFadeInterval = null;
        let currentBgmName = '';
        let saveLoadMode = 'load';
        const RESOLVED_IMAGE_ASSETS = {{}};
        const RESOLVED_AUDIO_ASSETS = {{}};
        const ASSET_FETCH_PROMISES = new Map();
        const LOCAL_ASSET_SCRIPT_PROMISES = new Map();
        let resolvedFaviconHref = '';
        const FULLSCREEN_EXPAND_ICON = '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
        const FULLSCREEN_EXIT_ICON = '<path d="M9 4H4v5M20 9V4h-5M15 20h5v-5M4 15v5h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
        let currentSceneScriptRuntimeId = 0;
        
        let gameState = createInitialGameState();

        function getFullscreenApiTarget() {{
            return document.documentElement;
        }}

        function getFullscreenElement() {{
            return document.fullscreenElement
                || document.webkitFullscreenElement
                || document.msFullscreenElement
                || null;
        }}

        function isFullscreenSupported() {{
            const target = getFullscreenApiTarget();
            return !!(
                target.requestFullscreen
                || target.webkitRequestFullscreen
                || target.msRequestFullscreen
            );
        }}

        function updateFullscreenButtons() {{
            const isFullscreen = !!getFullscreenElement();
            const label = isFullscreen ? '最大化を解除' : '最大化';
            const icon = isFullscreen ? FULLSCREEN_EXIT_ICON : FULLSCREEN_EXPAND_ICON;

            document.querySelectorAll('.fullscreen-button').forEach(button => {{
                button.classList.toggle('active', isFullscreen);
                button.classList.toggle('hidden', !isFullscreenSupported());
                button.title = label;
                button.setAttribute('aria-label', label);
                const svg = button.querySelector('svg');
                if (svg) {{
                    svg.innerHTML = icon;
                }}
            }});
        }}

        async function requestAppFullscreen() {{
            const target = getFullscreenApiTarget();
            if (target.requestFullscreen) return target.requestFullscreen();
            if (target.webkitRequestFullscreen) return target.webkitRequestFullscreen();
            if (target.msRequestFullscreen) return target.msRequestFullscreen();
            throw new Error('Fullscreen API is not supported');
        }}

        async function exitAppFullscreen() {{
            if (document.exitFullscreen) return document.exitFullscreen();
            if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
            if (document.msExitFullscreen) return document.msExitFullscreen();
            throw new Error('Fullscreen API is not supported');
        }}

        async function toggleFullscreen() {{
            if (!isFullscreenSupported()) return;
            try {{
                if (getFullscreenElement()) {{
                    await exitAppFullscreen();
                }} else {{
                    await requestAppFullscreen();
                }}
            }} catch (error) {{
                console.warn('Fullscreen toggle failed:', error);
            }} finally {{
                updateFullscreenButtons();
            }}
        }}

        function updateLoadingMessage(message) {{
            const text = document.querySelector('#loading-screen .loading-text');
            if (text) {{
                text.textContent = message;
            }}
        }}

        function updateLoadingCounts(imageLoaded, imageTotal, audioLoaded, audioTotal) {{
            const imageCount = document.getElementById('loading-image-count');
            const audioCount = document.getElementById('loading-audio-count');
            if (imageCount) {{
                imageCount.textContent = `画像: ${{imageLoaded}} / ${{imageTotal}}`;
            }}
            if (audioCount) {{
                audioCount.textContent = `音声: ${{audioLoaded}} / ${{audioTotal}}`;
            }}
        }}

        function restoreObfuscatedBytes(buffer, headerSwapSize) {{
            const bytes = new Uint8Array(buffer);
            const swapSize = Math.min(Number(headerSwapSize) || 0, bytes.length);
            for (let left = 0, right = swapSize - 1; left < right; left += 1, right -= 1) {{
                const temp = bytes[left];
                bytes[left] = bytes[right];
                bytes[right] = temp;
            }}
            return bytes;
        }}

        function decodeBase64ToBytes(base64Text) {{
            const normalized = String(base64Text || '').trim();
            if (!normalized) {{
                return new Uint8Array();
            }}

            const binary = atob(normalized);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i += 1) {{
                bytes[i] = binary.charCodeAt(i);
            }}
            return bytes;
        }}

        function getLocalAssetScriptPath(meta) {{
            if (!meta || !meta.path) {{
                return '';
            }}
            const filename = meta.path.split('/').pop();
            return `assets/{self.LOCAL_ASSET_SCRIPT_DIRNAME}/${{filename}}.js`;
        }}

        function loadLocalAssetScript(meta) {{
            window.__LUMINA_LOCAL_ASSET_PACK__ = window.__LUMINA_LOCAL_ASSET_PACK__ || {{}};
            if (window.__LUMINA_LOCAL_ASSET_PACK__[meta.path]) {{
                return Promise.resolve(window.__LUMINA_LOCAL_ASSET_PACK__);
            }}

            const scriptPath = getLocalAssetScriptPath(meta);
            if (!scriptPath) {{
                return Promise.resolve(window.__LUMINA_LOCAL_ASSET_PACK__);
            }}
            if (LOCAL_ASSET_SCRIPT_PROMISES.has(scriptPath)) {{
                return LOCAL_ASSET_SCRIPT_PROMISES.get(scriptPath);
            }}

            const promise = new Promise((resolve, reject) => {{
                const script = document.createElement('script');
                script.src = scriptPath;
                script.onload = () => resolve(window.__LUMINA_LOCAL_ASSET_PACK__ || {{}});
                script.onerror = () => reject(new Error(`Local asset script load failed: ${{scriptPath}}`));
                document.head.appendChild(script);
            }}).catch(error => {{
                console.warn(error);
                return window.__LUMINA_LOCAL_ASSET_PACK__ || {{}};
            }});

            LOCAL_ASSET_SCRIPT_PROMISES.set(scriptPath, promise);
            return promise;
        }}

        async function resolveObfuscatedAsset(meta) {{
            if (!meta || !meta.path) {{
                return '';
            }}

            const cacheKey = `${{meta.path}}::${{meta.mimeType || ''}}::${{meta.headerSwapSize || 0}}`;
            if (ASSET_FETCH_PROMISES.has(cacheKey)) {{
                return ASSET_FETCH_PROMISES.get(cacheKey);
            }}

            const task = (location.protocol === 'file:'
                ? loadLocalAssetScript(meta).then(bundle => {{
                    const payload = bundle[meta.path];
                    if (!payload) {{
                        throw new Error(`Local asset payload not found: ${{meta.path}}`);
                    }}
                    return decodeBase64ToBytes(payload).buffer;
                }})
                : fetch(meta.path).then(response => {{
                    if (!response.ok) {{
                        throw new Error(`Asset fetch failed: ${{meta.path}} (${{response.status}})`);
                    }}
                    return response.arrayBuffer();
                }}))
                .then(buffer => {{
                    const restored = restoreObfuscatedBytes(buffer, meta.headerSwapSize);
                    const blob = new Blob([restored], {{ type: meta.mimeType || 'application/octet-stream' }});
                    return URL.createObjectURL(blob);
                }})
                .catch(error => {{
                    console.warn('Asset restore failed:', meta.path, error);
                    return '';
                }});

            ASSET_FETCH_PROMISES.set(cacheKey, task);
            return task;
        }}

        async function resolveImageAsset(name) {{
            if (!name || !(name in ASSETS)) {{
                return '';
            }}
            if (RESOLVED_IMAGE_ASSETS[name]) {{
                return RESOLVED_IMAGE_ASSETS[name];
            }}
            const url = await resolveObfuscatedAsset(ASSETS[name]);
            if (url) {{
                RESOLVED_IMAGE_ASSETS[name] = url;
            }}
            return url;
        }}

        async function resolveAudioAsset(name) {{
            if (!name || !(name in AUDIO_ASSETS)) {{
                return '';
            }}
            if (RESOLVED_AUDIO_ASSETS[name]) {{
                return RESOLVED_AUDIO_ASSETS[name];
            }}
            const url = await resolveObfuscatedAsset(AUDIO_ASSETS[name]);
            if (url) {{
                RESOLVED_AUDIO_ASSETS[name] = url;
            }}
            return url;
        }}

        function getResolvedImageAsset(name) {{
            return name ? (RESOLVED_IMAGE_ASSETS[name] || '') : '';
        }}

        function getResolvedAudioAsset(name) {{
            return name ? (RESOLVED_AUDIO_ASSETS[name] || '') : '';
        }}

        function preloadImageAsset(src) {{
            return new Promise(resolve => {{
                if (!src) {{
                    resolve();
                    return;
                }}

                const img = new Image();
                const finish = () => resolve();
                img.onload = finish;
                img.onerror = finish;
                img.src = src;
            }});
        }}

        function preloadAudioAsset(src) {{
            return new Promise(resolve => {{
                if (!src) {{
                    resolve();
                    return;
                }}

                const audio = new Audio();
                let settled = false;

                const finish = () => {{
                    if (settled) return;
                    settled = true;
                    audio.removeEventListener('loadeddata', finish);
                    audio.removeEventListener('canplaythrough', finish);
                    audio.removeEventListener('error', finish);
                    resolve();
                }};

                audio.preload = 'auto';
                audio.addEventListener('loadeddata', finish, {{ once: true }});
                audio.addEventListener('canplaythrough', finish, {{ once: true }});
                audio.addEventListener('error', finish, {{ once: true }});
                audio.src = src;

                try {{
                    audio.load();
                }} catch (error) {{
                    finish();
                }}

                setTimeout(finish, 3000);
            }});
        }}

        async function preloadLoadingAssets() {{
            const imageNames = Object.keys(ASSETS);
            const audioNames = Object.keys(AUDIO_ASSETS);
            const imageTotal = imageNames.length;
            const audioTotal = audioNames.length;
            let imageLoaded = 0;
            let audioLoaded = 0;

            updateLoadingCounts(imageLoaded, imageTotal, audioLoaded, audioTotal);
            updateLoadingMessage('画像と音声を読み込んでいます...');

            const imageTasks = imageNames.map(name =>
                resolveImageAsset(name)
                .then(src => preloadImageAsset(src))
                .finally(() => {{
                    imageLoaded += 1;
                    updateLoadingCounts(imageLoaded, imageTotal, audioLoaded, audioTotal);
                }})
            );
            const audioTasks = audioNames.map(name =>
                resolveAudioAsset(name)
                .then(src => preloadAudioAsset(src))
                .finally(() => {{
                    audioLoaded += 1;
                    updateLoadingCounts(imageLoaded, imageTotal, audioLoaded, audioTotal);
                }})
            );

            await Promise.all([...imageTasks, ...audioTasks]);
        }}

        async function resolveFaviconHref() {{
            if (!FAVICON_ASSET || Object.keys(FAVICON_ASSET).length === 0) {{
                return '';
            }}
            if (FAVICON_ASSET.href) {{
                return FAVICON_ASSET.href;
            }}
            if (resolvedFaviconHref) {{
                return resolvedFaviconHref;
            }}
            resolvedFaviconHref = await resolveObfuscatedAsset(FAVICON_ASSET);
            return resolvedFaviconHref;
        }}

        async function applyFavicon() {{
            const href = await resolveFaviconHref();
            if (!href) {{
                return;
            }}

            let link = document.querySelector('link[rel="icon"]');
            if (!link) {{
                link = document.createElement('link');
                link.rel = 'icon';
                document.head.appendChild(link);
            }}
            link.href = href;
        }}

        async function initializeGame() {{
            updateLoadingMessage('設定を読み込んでいます...');

            loadSettings();
            loadLicenseAcceptance();
            initCustomNameUI();
            migrateLegacySaveData();

            await preloadLoadingAssets();
            await applyFavicon();

            const titleBg = extractAssetName(CONFIG.title_bg_image);
            const titleBgUrl = getResolvedImageAsset(titleBg);
            if (titleBgUrl) {{
                document.getElementById('title-screen').style.backgroundImage = `url(${{titleBgUrl}})`;
            }}
            updateLoadingMessage('ロード完了');

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
        }}
        
        // 初期化
        document.addEventListener('DOMContentLoaded', () => {{
            console.log('LuminasScript initialized');
            console.log(`Loaded ${{SCENARIO_DATA.length}} scenes`);
            console.log(`Loaded ${{Object.keys(ASSETS).length}} assets`);
            console.log(`Loaded ${{Object.keys(AUDIO_ASSETS).length}} bgm assets`);
            updateFullscreenButtons();
            document.addEventListener('fullscreenchange', updateFullscreenButtons);
            document.addEventListener('webkitfullscreenchange', updateFullscreenButtons);
            document.addEventListener('MSFullscreenChange', updateFullscreenButtons);
            document.addEventListener('keydown', handleSceneNavigationKeydown);
            initializeGame().catch(error => {{
                console.error('Initialization failed:', error);
                updateLoadingMessage('ロードに失敗しました');
            }});
        }});
        
        // クリック遅延ゲージの更新
        function startClickDelay(scene) {{
            canClick = false;
            const gauge = document.getElementById('click-gauge');
            gauge.style.width = '0%';
            
            const delay = getSceneClickDelay(scene);
            let progress = 0;
            const interval = 10;
            const increment = (100 / delay) * interval;
            
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
                autoAdvance(SCENARIO_DATA[currentSceneIndex]);
            }} else {{
                btn.classList.remove('active');
                if (autoModeTimeout) {{
                    clearTimeout(autoModeTimeout);
                    autoModeTimeout = null;
                }}
            }}
        }}
        
        function autoAdvance(scene) {{
            if (!isAutoMode) return;
            
            autoModeTimeout = setTimeout(() => {{
                if (isAutoMode && canClick && !isNoticeModalOpen()) {{
                    loadScene(findNextSceneIndex(currentSceneIndex));
                }}
            }}, getSceneAutoSceneChangeDelay(scene));
        }}

        function normalizeSceneId(sceneId) {{
            return (sceneId || '').trim();
        }}

        function normalizeNoticeText(value) {{
            return String(value || '')
                .replace(/\\r\\n?/g, '\\n')
                .replace(/\\\\n/g, '\\n')
                .replace(/\\n/g, '\\n')
                .replace(/<br\\s*\\/?>/giu, '\\n')
                .replace(/\\[br\\]/giu, '\\n')
                .trim();
        }}

        function normalizeStateStoreKey(value) {{
            return String(value || '').trim();
        }}

        function createEmptySceneScriptDirectives() {{
            return {{
                tokens: [],
                overrides: {{ jumpTargets: {{}} }},
                noticeMessages: []
            }};
        }}

        function loadStateStore() {{
            const raw = safeStorageGet(STATE_STORE_KEY);
            if (!raw) {{
                return {{}};
            }}

            try {{
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {{
                    return parsed;
                }}
            }} catch (e) {{
                console.warn('状態ストアの読み込みに失敗しました:', e);
            }}

            return {{}};
        }}

        function saveStateStore(stateStore) {{
            return safeStorageSet(STATE_STORE_KEY, JSON.stringify(stateStore || {{}}));
        }}

        function getStateStoreValue(stateStore, key) {{
            if (!stateStore || typeof stateStore !== 'object') return undefined;
            if (!key || !Object.prototype.hasOwnProperty.call(stateStore, key)) return undefined;
            return stateStore[key];
        }}

        function splitTopLevelScriptTokens(text, delimiters) {{
            const tokens = [];
            let current = '';
            let parenDepth = 0;

            for (const char of String(text || '')) {{
                if (char === '(') {{
                    parenDepth += 1;
                    current += char;
                    continue;
                }}
                if (char === ')') {{
                    parenDepth = Math.max(0, parenDepth - 1);
                    current += char;
                    continue;
                }}
                if (parenDepth === 0 && delimiters.has(char)) {{
                    const trimmed = current.trim();
                    if (trimmed) {{
                        tokens.push(trimmed);
                    }}
                    current = '';
                    continue;
                }}
                current += char;
            }}

            const trimmed = current.trim();
            if (trimmed) {{
                tokens.push(trimmed);
            }}

            return tokens;
        }}

        function splitSceneScriptSegment(segment) {{
            const primaryChunks = splitTopLevelScriptTokens(
                segment,
                new Set([',', ';', '|', '\\n', '\\r'])
            );

            return primaryChunks.flatMap(chunk => {{
                const trimmed = chunk.trim();
                if (!trimmed) return [];
                if (
                    /^NOTICE\\s*\\(/iu.test(trimmed)
                    || /^STATE_(?:EQ|LEN_GTE|CONTAINS)\\([^)]*\\)\\s*=\\s*NOTICE\\s*\\(/iu.test(trimmed)
                ) {{
                    return [trimmed];
                }}
                return splitTopLevelScriptTokens(trimmed, new Set([' ', '\\t']));
            }});
        }}

        function parseStateStoreValueSpec(value) {{
            return String(value || '').trim();
        }}

        function parseStateStoreKeyValueArgs(args) {{
            const raw = String(args || '').trim();
            const separatorIndex = raw.indexOf(':');
            if (separatorIndex <= 0) return null;

            const key = normalizeStateStoreKey(raw.slice(0, separatorIndex));
            const value = parseStateStoreValueSpec(raw.slice(separatorIndex + 1));
            if (!key) return null;
            return {{ key, value }};
        }}

        function parseStateActionToken(token) {{
            const match = String(token || '').trim().match(/^STATE_(SET|REMOVE|APPEND)\\((.*)\\)$/iu);
            if (!match) return null;

            const action = match[1].toUpperCase();
            const args = match[2];
            if (action === 'REMOVE') {{
                const key = normalizeStateStoreKey(args);
                return key ? {{ type: 'stateAction', action, key }} : null;
            }}

            const parsedArgs = parseStateStoreKeyValueArgs(args);
            if (!parsedArgs) return null;
            return {{
                type: 'stateAction',
                action,
                key: parsedArgs.key,
                value: parsedArgs.value
            }};
        }}

        function parseStateConditionToken(token) {{
            const match = String(token || '').trim().match(/^STATE_(EQ|LEN_GTE|CONTAINS)\\((.*)\\)\\s*=\\s*(.+)$/iu);
            if (!match) return null;

            const condition = match[1].toUpperCase();
            const args = match[2];
            const directive = String(match[3] || '').trim();
            if (!directive) return null;

            const parsedArgs = parseStateStoreKeyValueArgs(args);
            if (!parsedArgs) return null;

            if (condition === 'LEN_GTE') {{
                const threshold = Number.parseInt(parsedArgs.value, 10);
                if (!Number.isFinite(threshold) || threshold < 0) {{
                    return null;
                }}
                return {{
                    type: 'conditionalDirective',
                    condition,
                    key: parsedArgs.key,
                    value: threshold,
                    directive
                }};
            }}

            return {{
                type: 'conditionalDirective',
                condition,
                key: parsedArgs.key,
                value: parsedArgs.value,
                directive
            }};
        }}

        function parseSceneScriptEntries(scene) {{
            if (!scene || typeof scene !== 'object') {{
                return {{ entries: [] }};
            }}

            const raw = String(scene.script || '');
            if (scene._parsedScriptSource === raw && scene._parsedScriptEntries) {{
                return scene._parsedScriptEntries;
            }}

            const segments = [];
            const outside = raw.replace(/<([^>]*)>/gu, (_, inner) => {{
                if (inner && inner.trim()) {{
                    segments.push(inner);
                }}
                return ' ';
            }});
            if (outside.trim()) {{
                segments.push(outside);
            }}

            const parsed = {{
                entries: segments
                    .flatMap(segment => splitSceneScriptSegment(segment))
                    .map(token => parseStateConditionToken(token) || parseStateActionToken(token) || {{
                        type: 'directive',
                        directive: String(token || '').trim()
                    }})
                    .filter(entry => entry && (entry.directive || entry.key))
            }};
            scene._parsedScriptSource = raw;
            scene._parsedScriptEntries = parsed;
            return parsed;
        }}

        function applySceneDirectiveText(target, directiveText) {{
            const raw = String(directiveText || '').trim();
            if (!raw) return;

            const noticeFunctionMatch = raw.match(/^NOTICE\\((.*)\\)$/iu);
            if (noticeFunctionMatch) {{
                const normalizedValue = normalizeNoticeText(noticeFunctionMatch[1]);
                if (normalizedValue) {{
                    target.noticeMessages.push(normalizedValue);
                }}
                return;
            }}

            const jumpFunctionMatch = raw.match(/^JUMP_([ABCD])\\((.*)\\)$/iu);
            if (jumpFunctionMatch) {{
                const branch = jumpFunctionMatch[1].trim().toUpperCase();
                const targetSceneId = normalizeSceneId(jumpFunctionMatch[2]);
                if (targetSceneId) {{
                    target.overrides.jumpTargets[branch] = targetSceneId;
                }}
                return;
            }}

            const functionStyleMatch = raw.match(/^(CLICK_DELAY|AUTO_SCENE_CHANGE_DELAY)\\((.*)\\)$/iu);
            if (functionStyleMatch) {{
                const key = functionStyleMatch[1].trim().toUpperCase();
                const value = functionStyleMatch[2].trim();
                const parsed = parsePositiveInt(value, null);
                if (key === 'CLICK_DELAY') {{
                    if (parsed !== null) {{
                        target.overrides.clickDelay = parsed;
                    }}
                    return;
                }}
                if (key === 'AUTO_SCENE_CHANGE_DELAY') {{
                    if (parsed !== null) {{
                        target.overrides.autoSceneChangeDelay = parsed;
                    }}
                    return;
                }}
            }}

            const separatorIndex = raw.indexOf('=');
            if (separatorIndex <= 0) {{
                target.tokens.push(raw.toUpperCase());
                return;
            }}

            const key = raw.slice(0, separatorIndex).trim().toUpperCase();
            const value = raw.slice(separatorIndex + 1).trim();
            if (!key) return;

            const parsed = parsePositiveInt(value, null);
            if (key === 'CLICK_DELAY') {{
                if (parsed !== null) {{
                    target.overrides.clickDelay = parsed;
                }}
                return;
            }}
            if (key === 'AUTO_SCENE_CHANGE_DELAY') {{
                if (parsed !== null) {{
                    target.overrides.autoSceneChangeDelay = parsed;
                }}
                return;
            }}

            target.tokens.push(`${{key}}=${{value}}`);
        }}

        function applyStateActionToStore(stateStore, entry) {{
            if (!entry || entry.type !== 'stateAction' || !entry.key) {{
                return false;
            }}

            if (entry.action === 'SET') {{
                stateStore[entry.key] = String(entry.value || '');
                return true;
            }}

            if (entry.action === 'REMOVE') {{
                if (!Object.prototype.hasOwnProperty.call(stateStore, entry.key)) {{
                    return false;
                }}
                delete stateStore[entry.key];
                return true;
            }}

            if (entry.action === 'APPEND') {{
                const currentValue = getStateStoreValue(stateStore, entry.key);
                if (currentValue === undefined) {{
                    stateStore[entry.key] = [String(entry.value || '')];
                    return true;
                }}
                if (!Array.isArray(currentValue)) {{
                    console.warn(`STATE_APPEND requires an array value: ${{entry.key}}`);
                    return false;
                }}
                currentValue.push(String(entry.value || ''));
                return true;
            }}

            return false;
        }}

        function evaluateStateCondition(stateStore, entry) {{
            if (!entry || entry.type !== 'conditionalDirective' || !entry.key) {{
                return false;
            }}

            const currentValue = getStateStoreValue(stateStore, entry.key);
            if (entry.condition === 'EQ') {{
                if (Array.isArray(currentValue) || currentValue === undefined) {{
                    return false;
                }}
                return String(currentValue) === String(entry.value);
            }}

            if (entry.condition === 'LEN_GTE') {{
                return Array.isArray(currentValue) && currentValue.length >= entry.value;
            }}

            if (entry.condition === 'CONTAINS') {{
                return Array.isArray(currentValue)
                    && currentValue.some(value => String(value) === String(entry.value));
            }}

            return false;
        }}

        function resolveSceneScriptDirectives(scene) {{
            if (!scene || typeof scene !== 'object') {{
                return {{ tokens: [], overrides: {{ jumpTargets: {{}} }}, notice: '' }};
            }}

            if (
                scene._resolvedScriptRuntimeId === currentSceneScriptRuntimeId
                && scene._resolvedScriptDirectives
            ) {{
                return scene._resolvedScriptDirectives;
            }}

            const parsed = parseSceneScriptEntries(scene);
            const target = createEmptySceneScriptDirectives();
            const stateStore = loadStateStore();
            let stateStoreDirty = false;

            parsed.entries.forEach(entry => {{
                if (entry.type === 'stateAction') {{
                    stateStoreDirty = applyStateActionToStore(stateStore, entry) || stateStoreDirty;
                    return;
                }}

                if (entry.type === 'conditionalDirective') {{
                    if (evaluateStateCondition(stateStore, entry)) {{
                        applySceneDirectiveText(target, entry.directive);
                    }}
                    return;
                }}

                applySceneDirectiveText(target, entry.directive);
            }});

            if (stateStoreDirty) {{
                saveStateStore(stateStore);
            }}

            const resolved = {{
                tokens: target.tokens,
                overrides: target.overrides,
                notice: target.noticeMessages.join('\\n\\n')
            }};
            scene._resolvedScriptRuntimeId = currentSceneScriptRuntimeId;
            scene._resolvedScriptDirectives = resolved;
            return resolved;
        }}

        function parseSceneScriptTokens(scene) {{
            return resolveSceneScriptDirectives(scene).tokens;
        }}

        function sceneHasDirective(scene, directive) {{
            if (!directive) return false;
            return parseSceneScriptTokens(scene).includes(String(directive).trim().toUpperCase());
        }}

        function getSceneClickDelay(scene) {{
            const value = resolveSceneScriptDirectives(scene).overrides.clickDelay;
            return parsePositiveInt(value, CLICK_DELAY);
        }}

        function getSceneAutoSceneChangeDelay(scene) {{
            const value = resolveSceneScriptDirectives(scene).overrides.autoSceneChangeDelay;
            return parsePositiveInt(
                value,
                parsePositiveInt(gameState.settings.autoSceneChangeDelay, AUTO_SCENE_CHANGE_DELAY)
            );
        }}

        function getSceneNoticeText(scene) {{
            return resolveSceneScriptDirectives(scene).notice || '';
        }}

        function getChoiceJumpTarget(scene, branchLetter) {{
            const jumpTargets = resolveSceneScriptDirectives(scene).overrides.jumpTargets || {{}};
            return normalizeSceneId(jumpTargets[branchLetter] || '');
        }}

        function isNoticeModalOpen() {{
            const modal = document.getElementById('notice-modal');
            return !!(modal && !modal.classList.contains('hidden'));
        }}

        function showNoticeModal(message) {{
            const modal = document.getElementById('notice-modal');
            const textEl = document.getElementById('notice-text');
            if (!modal || !textEl) return;
            textEl.textContent = String(message || '');
            modal.classList.remove('hidden');
        }}

        function closeNoticeModal(options = {{}}) {{
            const resumeAuto = options.resumeAuto !== false;
            const modal = document.getElementById('notice-modal');
            if (modal) {{
                modal.classList.add('hidden');
            }}

            if (!resumeAuto || !isAutoMode) return;

            const scene = SCENARIO_DATA[currentSceneIndex];
            if (!scene) return;

            if (autoModeTimeout) {{
                clearTimeout(autoModeTimeout);
                autoModeTimeout = null;
            }}

            if (getSceneType(scene.scene_id) === 'ending') {{
                autoModeTimeout = setTimeout(() => {{
                    if (isAutoMode && canClick && !isNoticeModalOpen()) {{
                        returnToTitle();
                    }}
                }}, getSceneAutoSceneChangeDelay(scene));
                return;
            }}

            if (getSceneType(scene.scene_id) === 'dialogue') {{
                autoAdvance(scene);
            }}
        }}

        function isSceneAdvanceBlockedModalOpen() {{
            return [
                'history-screen',
                'game-menu',
                'save-load-screen',
                'settings-screen',
                'license-modal',
                'custom-name-modal',
                'credits-screen'
            ].some(id => {{
                const element = document.getElementById(id);
                return element && !element.classList.contains('hidden');
            }});
        }}

        function isInteractiveElementFocused() {{
            const activeElement = document.activeElement;
            if (!activeElement || activeElement === document.body) {{
                return false;
            }}

            const tagName = String(activeElement.tagName || '').toUpperCase();
            if (['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'A'].includes(tagName)) {{
                return true;
            }}

            return !!activeElement.isContentEditable;
        }}

        function isSceneNavigationKeyEventAllowed() {{
            const gameScreen = document.getElementById('game-screen');
            if (!gameScreen || !gameScreen.classList.contains('active')) return false;
            if (isNoticeModalOpen() || isSceneAdvanceBlockedModalOpen() || isInteractiveElementFocused()) return false;
            return true;
        }}

        function normalizeSceneNavigationEntry(entry) {{
            const sceneIndex = Number.parseInt(entry?.sceneIndex, 10);
            const historyLengthBefore = Number.parseInt(entry?.historyLengthBefore, 10);
            if (!Number.isInteger(sceneIndex) || sceneIndex < 0 || sceneIndex >= SCENARIO_DATA.length) {{
                return null;
            }}
            return {{
                sceneIndex,
                historyLengthBefore: Number.isInteger(historyLengthBefore) && historyLengthBefore >= 0
                    ? historyLengthBefore
                    : 0
            }};
        }}

        function normalizeConversationHistoryEntry(entry) {{
            const speaker = entry && typeof entry.speaker === 'string' ? entry.speaker : '';
            const text = entry && typeof entry.text === 'string' ? entry.text : '';
            const sceneHistoryPosition = Number.parseInt(entry?.sceneHistoryPosition, 10);
            return {{
                speaker,
                text,
                sceneHistoryPosition: Number.isInteger(sceneHistoryPosition) ? sceneHistoryPosition : -1
            }};
        }}

        function recordSceneNavigation(index) {{
            const lastEntry = sceneNavigationHistory[sceneNavigationHistory.length - 1];
            if (lastEntry && lastEntry.sceneIndex === index) {{
                return;
            }}

            sceneNavigationHistory.push({{
                sceneIndex: index,
                historyLengthBefore: conversationHistory.length
            }});
        }}

        function getLatestChoiceHistoryPosition() {{
            for (let i = sceneNavigationHistory.length - 1; i >= 0; i -= 1) {{
                const entry = sceneNavigationHistory[i];
                const scene = SCENARIO_DATA[entry.sceneIndex];
                if (scene && getSceneType(scene.scene_id) === 'choice') {{
                    return i;
                }}
            }}
            return -1;
        }}

        function getCurrentSceneHistoryPosition() {{
            return sceneNavigationHistory.length - 1;
        }}

        function inferHistoryEntryScenePosition(historyIndex) {{
            if (!Number.isInteger(historyIndex) || historyIndex < 0) {{
                return -1;
            }}

            let resolvedPosition = -1;
            for (let i = 0; i < sceneNavigationHistory.length; i += 1) {{
                const entry = sceneNavigationHistory[i];
                if (!entry || historyIndex < entry.historyLengthBefore) {{
                    break;
                }}
                resolvedPosition = i;
            }}
            return resolvedPosition;
        }}

        function getHistoryEntryScenePosition(item, historyIndex) {{
            const normalizedPosition = Number.parseInt(item?.sceneHistoryPosition, 10);
            if (
                Number.isInteger(normalizedPosition) &&
                normalizedPosition >= 0 &&
                normalizedPosition < sceneNavigationHistory.length
            ) {{
                return normalizedPosition;
            }}
            return inferHistoryEntryScenePosition(historyIndex);
        }}

        function canGoBackToSceneHistoryPosition(targetPosition) {{
            if (!Number.isInteger(targetPosition) || targetPosition < 0 || targetPosition >= sceneNavigationHistory.length) {{
                return false;
            }}

            if (targetPosition >= getCurrentSceneHistoryPosition()) {{
                return false;
            }}

            const choiceBoundary = getLatestChoiceHistoryPosition();
            if (choiceBoundary !== -1 && targetPosition <= choiceBoundary) {{
                return false;
            }}

            return true;
        }}

        function canGoBackOneScene() {{
            if (sceneNavigationHistory.length < 2) {{
                return false;
            }}
            const targetPosition = sceneNavigationHistory.length - 2;
            return canGoBackToSceneHistoryPosition(targetPosition);
        }}

        function goBackToSceneHistoryPosition(targetPosition) {{
            if (!canGoBackToSceneHistoryPosition(targetPosition)) {{
                return false;
            }}

            const targetEntry = sceneNavigationHistory[targetPosition];
            if (!targetEntry) {{
                return false;
            }}

            sceneNavigationHistory = sceneNavigationHistory.slice(0, targetPosition + 1);
            conversationHistory = conversationHistory.slice(0, targetEntry.historyLengthBefore);
            loadScene(targetEntry.sceneIndex, {{ recordHistory: false }});
            return true;
        }}

        function goBackOneScene() {{
            if (sceneNavigationHistory.length < 2) {{
                return false;
            }}
            return goBackToSceneHistoryPosition(sceneNavigationHistory.length - 2);
        }}

        function goBackFromHistory() {{
            if (!goBackOneScene()) {{
                return;
            }}
            closeHistory();
        }}

        function handleSceneNavigationKeydown(event) {{
            if (event.repeat) return;
            if (event.key !== 'Enter' && event.key !== 'Backspace') return;
            if (!isSceneNavigationKeyEventAllowed()) return;

            const scene = SCENARIO_DATA[currentSceneIndex];
            if (!scene) return;

            const sceneType = getSceneType(scene.scene_id);
            if (event.key === 'Backspace') {{
                event.preventDefault();
                goBackOneScene();
                return;
            }}

            if (sceneType === 'choice') {{
                event.preventDefault();
                return;
            }}

            if (!canClick) return;

            event.preventDefault();
            if (sceneType === 'ending') {{
                returnToTitle();
                return;
            }}

            if (sceneType === 'dialogue') {{
                loadScene(findNextSceneIndex(currentSceneIndex));
            }}
        }}

        function showSceneNotice(scene) {{
            const message = getSceneNoticeText(scene);
            if (!message) {{
                return false;
            }}
            showNoticeModal(message);
            return true;
        }}

        function updateTextBoxAppearance(scene) {{
            const textBox = document.getElementById('text-box');
            const gaugeContainer = document.getElementById('click-gauge-container');
            const gauge = document.getElementById('click-gauge');
            const isTextBackOff = sceneHasDirective(scene, 'TEXT_BACK_OFF');

            textBox.classList.toggle('text-back-off', isTextBackOff);
            gaugeContainer.classList.toggle('text-back-off', isTextBackOff);
            gauge.classList.toggle('text-back-off', isTextBackOff);
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

        function createInitialGameState() {{
            return {{
                currentSceneId: null,
                visitedScenes: [],
                choices: {{}},
                settings: {{ ...DEFAULT_SETTINGS }}
            }};
        }}

        function getStorageKey(name) {{
            return STORAGE_PREFIX ? `${{STORAGE_PREFIX}}_${{name}}` : name;
        }}

        function getSaveSlotKey(slotIndex) {{
            return `${{SAVE_SLOT_KEY_PREFIX}}${{String(slotIndex).padStart(2, '0')}}`;
        }}

        function getSaveSlotLabel(slotIndex) {{
            return `Slot ${{String(slotIndex).padStart(2, '0')}}`;
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

        function formatSaveTimestamp(value) {{
            if (!value) return '';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return '';
            return date.toLocaleString('ja-JP', {{
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            }});
        }}

        function summarizeSceneText(raw) {{
            const normalized = applyCustomName(raw || '').replace(/\\s+/g, ' ').trim();
            if (!normalized) return '';
            return normalized.length > 60 ? `${{normalized.slice(0, 60)}}...` : normalized;
        }}

        function getSceneSpeakerName(scene) {{
            return applyCustomName(scene?.person_name || '');
        }}

        function getSavePreviewMeta(data) {{
            const sceneIndex = Number.parseInt(data?.sceneIndex, 10);
            const scene = Number.isInteger(sceneIndex) ? SCENARIO_DATA[sceneIndex] : null;
            const meta = data?.meta && typeof data.meta === 'object' ? data.meta : {{}};
            return {{
                sceneId: meta.sceneId || normalizeSceneId(scene?.scene_id),
                speaker: applyCustomName(meta.speaker || getSceneSpeakerName(scene)),
                preview: meta.preview || summarizeSceneText(scene?.text || '')
            }};
        }}

        function readSaveSlot(slotIndex) {{
            const raw = safeStorageGet(getSaveSlotKey(slotIndex));
            if (!raw) return null;
            try {{
                return JSON.parse(raw);
            }} catch (e) {{
                console.warn(`セーブスロット ${{slotIndex}} の読み込みに失敗しました:`, e);
                return null;
            }}
        }}

        function migrateLegacySaveData() {{
            const legacyData = safeStorageGet(LEGACY_SAVE_DATA_KEY);
            if (!legacyData) return;

            const firstSlotKey = getSaveSlotKey(1);
            if (!safeStorageGet(firstSlotKey)) {{
                safeStorageSet(firstSlotKey, legacyData);
            }}
            safeStorageRemove(LEGACY_SAVE_DATA_KEY);
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
                let fontSize = null;
                let centered = false;

                parts.forEach(p => {{
                    if (/^#([0-9a-fA-F]{{3}}|[0-9a-fA-F]{{6}})$/.test(p)) {{
                        if (!color) color = p;
                    }} else if (/^S\\d+(\\.\\d+)?$/i.test(p)) {{
                        const sizeValue = Number.parseFloat(p.slice(1));
                        if (!Number.isNaN(sizeValue) && sizeValue > 0) {{
                            fontSize = sizeValue;
                        }}
                    }} else if (p.toUpperCase() === 'C') {{
                        centered = true;
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
                if (fontSize !== null) {{
                    formatted = `<span style="font-size:${{fontSize}}%;">${{formatted}}</span>`;
                }}
                if (centered) {{
                    formatted = `<span style="display:flex;align-items:center;justify-content:center;width:100%;text-align:center;">${{formatted}}</span>`;
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
        function addToHistory(speaker, text, options = {{}}) {{
            if (text && text.trim()) {{
                const requestedSceneHistoryPosition = Number.parseInt(options?.sceneHistoryPosition, 10);
                const sceneHistoryPosition = Number.isInteger(requestedSceneHistoryPosition)
                    ? requestedSceneHistoryPosition
                    : getCurrentSceneHistoryPosition();
                conversationHistory.push({{
                    speaker: applyCustomName(speaker),
                    text,
                    sceneHistoryPosition
                }});
            }}
        }}

        function jumpToHistoryEntry(historyIndex) {{
            const item = conversationHistory[historyIndex];
            const targetPosition = getHistoryEntryScenePosition(item, historyIndex);
            if (!goBackToSceneHistoryPosition(targetPosition)) {{
                return;
            }}
            closeHistory();
        }}
        
        // 会話履歴の表示
        function toggleHistory() {{
            const historyScreen = document.getElementById('history-screen');
            const historyList = document.getElementById('history-list');
            const historyHelpText = document.getElementById('history-help-text');
            const currentPosition = getCurrentSceneHistoryPosition();
            
            historyList.innerHTML = '';
            conversationHistory.forEach((item, index) => {{
                const div = document.createElement('div');
                div.className = 'history-item';
                const targetPosition = getHistoryEntryScenePosition(item, index);
                const isJumpable = canGoBackToSceneHistoryPosition(targetPosition);
                const isCurrentSceneItem = targetPosition === currentPosition;

                if (isJumpable) {{
                    div.classList.add('jumpable');
                    div.tabIndex = 0;
                    div.setAttribute('role', 'button');
                    div.setAttribute('aria-label', 'この位置に戻る');
                    div.title = 'クリックでこの位置に戻る';
                    div.onclick = () => jumpToHistoryEntry(index);
                    div.onkeydown = (event) => {{
                        if (event.key === 'Enter' || event.key === ' ') {{
                            event.preventDefault();
                            jumpToHistoryEntry(index);
                        }}
                    }};
                }} else {{
                    div.classList.add('locked');
                }}

                if (isCurrentSceneItem) {{
                    div.classList.add('current');
                }}
                
                if (item.speaker) {{
                    const speaker = document.createElement('div');
                    speaker.className = 'history-speaker';
                    speaker.textContent = applyCustomName(item.speaker);
                    div.appendChild(speaker);
                }}
                
                const text = document.createElement('div');
                text.className = 'history-text';
                text.innerHTML = formatText(item.text);
                div.appendChild(text);
                
                historyList.appendChild(div);
            }});

            if (historyHelpText) {{
                historyHelpText.textContent = canGoBackOneScene()
                    ? '戻りたい履歴をクリックしてください。選択肢より前には戻れません。'
                    : '現在の位置から戻れる履歴はありません。';
            }}
            
            historyScreen.classList.remove('hidden');
            // 最新の履歴までスクロール
            historyList.scrollTop = historyList.scrollHeight;
        }}

        function closeModalById(id) {{
            const element = document.getElementById(id);
            if (element) {{
                element.classList.add('hidden');
            }}
        }}
        
        function closeHistory() {{
            closeModalById('history-screen');
        }}
        
        // ゲーム開始
        function startNewGame() {{
            if (isLicenseRequired() && !licenseAccepted) {{
                showLicenseModal(true);
                return;
            }}
            currentSceneIndex = 0;
            conversationHistory = [];
            sceneNavigationHistory = [];
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
            dialogueText.style.fontSize = '1.2rem';
            dialogueText.style.textAlign = 'left';
            dialogueText.style.fontWeight = 'normal';
            updateTextBoxAppearance(null);
        }}
        
        // シーンを読み込み
        function loadScene(index, options = {{}}) {{
            if (index < 0) {{
                return;
            }}
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
            currentSceneScriptRuntimeId += 1;
            closeNoticeModal({{ resumeAuto: false }});
            const scene = SCENARIO_DATA[index];
            if (options.recordHistory !== false) {{
                recordSceneNavigation(index);
            }}
            resolveSceneScriptDirectives(scene);
            const sceneId = normalizeSceneId(scene.scene_id);
            gameState.currentSceneId = sceneId;
            gameState.visitedScenes.push(sceneId);
            resetSceneUI();
            clearCharacters();
            updateTextBoxAppearance(scene);
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
            updateEffectOverlay(scene.effect);
            showSceneNotice(scene);
            
            addToHistory('', chapterText);
            
            // 自動で次へ
            setTimeout(() => {{
                if (isNoticeModalOpen()) {{
                    const waitForNoticeToClose = () => {{
                        if (isNoticeModalOpen()) {{
                            setTimeout(waitForNoticeToClose, 100);
                            return;
                        }}
                        dialogueText.style.fontSize = '1.1rem';
                        dialogueText.style.textAlign = 'left';
                        dialogueText.style.fontWeight = 'normal';
                        loadScene(currentSceneIndex + 1);
                    }};
                    waitForNoticeToClose();
                    return;
                }}
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
            const activeElement = document.activeElement;
            
            textBox.style.display = 'none';
            choiceBox.classList.remove('hidden');
            choicesContainer.innerHTML = '';

            // 選択肢ページでは、Tabで選択肢にフォーカスするまでEnterを無効にする
            if (activeElement && typeof activeElement.blur === 'function') {{
                activeElement.blur();
            }}
            
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
            updateEffectOverlay(scene.effect);
            showSceneNotice(scene);
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
            const currentScene = SCENARIO_DATA[currentSceneIndex];
            const customJumpTarget = getChoiceJumpTarget(currentScene, branchLetter);
            const nextSceneId = customJumpTarget || baseParts.concat(branchLetter, '1').join('-');

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

            const speaker = getSceneSpeakerName(scene);
            speakerName.textContent = speaker;

            let text = applyCustomName(scene.text || '');
            const lines = text.split('\\n');
            if (lines.length > 4) {{
                text = lines.slice(0, 4).join('\\n');
            }}
            dialogueText.innerHTML = formatText(text);

            updateBackground(scene.background_image);
            updateCharacters(scene);
            updateEffectOverlay(scene.effect);
            showSceneNotice(scene);

            addToHistory(speaker, text);

            startClickDelay(scene);
            textBox.onclick = () => {{
                if (canClick) {{
                    returnToTitle();
                }}
            }};

            if (isAutoMode) {{
                autoModeTimeout = setTimeout(() => {{
                    if (isAutoMode && canClick && !isNoticeModalOpen()) {{
                        returnToTitle();
                    }}
                }}, getSceneAutoSceneChangeDelay(scene));
            }}
        }}
        
        // 通常の会話を表示
        function showDialogue(scene) {{
            const speakerName = document.getElementById('speaker-name');
            const dialogueText = document.getElementById('dialogue-text');
            const textBox = document.getElementById('text-box');
            
            textBox.style.display = 'block';
            document.getElementById('choice-box').classList.add('hidden');
            
            const speaker = getSceneSpeakerName(scene);
            speakerName.textContent = speaker;
            
            // テキストを4行に制限
            let text = applyCustomName(scene.text || '');
            const lines = text.split('\\n');
            if (lines.length > 4) {{
                text = lines.slice(0, 4).join('\\n');
            }}
            dialogueText.innerHTML = formatText(text);
            
            updateBackground(scene.background_image);
            updateCharacters(scene);
            updateEffectOverlay(scene.effect);
            showSceneNotice(scene);
            
            addToHistory(speaker, text);
            
            // クリック遅延を開始
            startClickDelay(scene);
            
            // クリックで次へ
            textBox.onclick = () => {{
                if (canClick) {{
                    loadScene(findNextSceneIndex(currentSceneIndex));
                }}
            }};
            
            // 自動モードの場合は自動で進む
            if (isAutoMode) {{
                autoAdvance(scene);
            }}
        }}

        const CHARACTER_BASE_SCALE = 3;
        const BACKGROUND_BASE_SCALE = 1;
        const EFFECT_BASE_SCALE = 1;

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
            const src = getResolvedAudioAsset(name);
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
            const resolved = getResolvedImageAsset(parsed.name);
            if (resolved) {{
                bgLayer.style.backgroundImage = `url(${{resolved}})`;
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

        function updateEffectOverlay(effectImage) {{
            const effectLayer = document.getElementById('effect-layer');
            const parsed = parseImageSpec(effectImage);
            const resolved = getResolvedImageAsset(parsed.name);
            if (resolved) {{
                effectLayer.style.backgroundImage = `url(${{resolved}})`;
                if (parsed.effects) {{
                    applyImageEffects(effectLayer, parsed.effects, EFFECT_BASE_SCALE);
                }} else {{
                    resetImageEffects(effectLayer, EFFECT_BASE_SCALE);
                }}
            }} else {{
                effectLayer.style.backgroundImage = '';
                resetImageEffects(effectLayer, EFFECT_BASE_SCALE);
            }}
        }}
        
        function updateCharacter(elementId, imageName) {{
            const element = document.getElementById(elementId);
            const parsed = parseImageSpec(imageName);
            const resolved = getResolvedImageAsset(parsed.name);
            if (resolved) {{
                element.style.backgroundImage = `url(${{resolved}})`;
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
            saveLoadMode = 'save';
            renderSaveSlots();
            document.getElementById('save-load-title').textContent = 'セーブ';
            document.getElementById('save-load-screen').classList.remove('hidden');
            closeGameMenu();
        }}
        
        function loadGame() {{
            if (isLicenseRequired() && !licenseAccepted) {{
                showLicenseModal(true);
                return;
            }}
            saveLoadMode = 'load';
            renderSaveSlots();
            document.getElementById('save-load-title').textContent = 'ロード';
            document.getElementById('save-load-screen').classList.remove('hidden');
            closeGameMenu();
        }}

        function closeSaveLoadModal() {{
            document.getElementById('save-load-screen').classList.add('hidden');
        }}

        function renderSaveSlots() {{
            const slotList = document.getElementById('save-slot-list');
            const summary = document.getElementById('save-load-summary');
            const tools = document.getElementById('save-load-tools');
            if (!slotList || !summary) return;
            if (tools) {{
                tools.classList.toggle('hidden', saveLoadMode !== 'load');
            }}

            let usedCount = 0;
            const rows = [];
            for (let slotIndex = 1; slotIndex <= SAVE_SLOT_COUNT; slotIndex += 1) {{
                const data = readSaveSlot(slotIndex);
                const hasData = !!data;
                if (hasData) usedCount += 1;

                const meta = hasData ? getSavePreviewMeta(data) : null;
                const timestamp = hasData ? formatSaveTimestamp(data.savedAt) : '';
                const primaryLabel = saveLoadMode === 'save'
                    ? (hasData ? '上書き保存' : 'ここに保存')
                    : 'ロード';
                const previewHtml = hasData
                    ? `
                        <div class="save-slot-scene">${{escapeHtml(meta.sceneId || 'scene unknown')}}</div>
                        <div class="save-slot-preview">${{escapeHtml(meta.speaker ? `${{meta.speaker}}: ${{meta.preview}}` : meta.preview || 'プレビューなし')}}</div>
                    `
                    : '<div class="save-slot-empty">未使用スロット</div>';

                rows.push(`
                    <div class="save-slot-item ${{hasData ? 'filled' : 'empty'}}">
                        <div class="save-slot-meta">
                            <div class="save-slot-header">
                                <span class="save-slot-number">${{getSaveSlotLabel(slotIndex)}}</span>
                                <span class="save-slot-time">${{escapeHtml(timestamp || '未保存')}}</span>
                            </div>
                            ${{previewHtml}}
                        </div>
                        <div class="save-slot-actions">
                            <button class="slot-action-btn" onclick="handleSaveLoadPrimaryAction(${{slotIndex}})" ${{saveLoadMode === 'load' && !hasData ? 'disabled' : ''}}>${{primaryLabel}}</button>
                            <button class="slot-action-btn danger" onclick="deleteSaveSlot(${{slotIndex}})" ${{hasData ? '' : 'disabled'}}>破棄</button>
                        </div>
                    </div>
                `);
            }}

            summary.textContent = `使用中 ${{usedCount}} / ${{SAVE_SLOT_COUNT}}`;
            slotList.innerHTML = rows.join('');
        }}

        function collectSaveBackupSlots() {{
            const slots = [];
            for (let slotIndex = 1; slotIndex <= SAVE_SLOT_COUNT; slotIndex += 1) {{
                const data = readSaveSlot(slotIndex);
                if (data) {{
                    slots.push({{ slot: slotIndex, data }});
                }}
            }}
            return slots;
        }}

        function exportSaveBackup() {{
            const slots = collectSaveBackupSlots();
            const backup = {{
                format: 'LuminasScriptSaveBackup',
                version: 1,
                exportedAt: new Date().toISOString(),
                saveSlotCount: SAVE_SLOT_COUNT,
                slots
            }};

            const json = JSON.stringify(backup, null, 2);
            const blob = new Blob([json], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\\..+/, '').replace('T', '_');
            anchor.href = url;
            anchor.download = `luminas_save_backup_${{stamp}}.json`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
        }}

        function promptImportSaveBackup() {{
            const input = document.getElementById('save-backup-input');
            if (!input) return;
            input.value = '';
            input.click();
        }}

        function normalizeImportedBackup(payload) {{
            if (payload && payload.format === 'LuminasScriptSaveBackup' && Array.isArray(payload.slots)) {{
                return payload.slots;
            }}
            if (Array.isArray(payload)) {{
                return payload;
            }}
            throw new Error('バックアップ形式が不正です');
        }}

        async function importSaveBackupFromFile(event) {{
            const input = event?.target;
            const file = input?.files?.[0];
            if (!file) return;

            try {{
                const text = await file.text();
                const payload = JSON.parse(text);
                const importedSlots = normalizeImportedBackup(payload);
                const validSlots = importedSlots.filter(entry => {{
                    const slot = Number.parseInt(entry?.slot, 10);
                    return Number.isInteger(slot) && slot >= 1 && slot <= SAVE_SLOT_COUNT && entry?.data && typeof entry.data === 'object';
                }});

                if (!validSlots.length) {{
                    throw new Error('有効なセーブデータが含まれていません');
                }}

                if (!confirm(`${{validSlots.length}} 件のセーブデータをインポートします。該当スロットは上書きされます。よろしいですか？`)) {{
                    return;
                }}

                let importedCount = 0;
                validSlots.forEach(entry => {{
                    const slot = Number.parseInt(entry.slot, 10);
                    const saved = safeStorageSet(getSaveSlotKey(slot), JSON.stringify(entry.data));
                    if (saved) {{
                        importedCount += 1;
                    }}
                }});

                renderSaveSlots();
                alert(`${{importedCount}} 件のセーブデータをインポートしました。`);
            }} catch (e) {{
                alert('インポートに失敗しました: ' + e.message);
            }} finally {{
                if (input) input.value = '';
            }}
        }}

        function buildSaveData() {{
            const scene = SCENARIO_DATA[currentSceneIndex] || null;
            return {{
                version: 2,
                savedAt: new Date().toISOString(),
                sceneIndex: currentSceneIndex,
                state: gameState,
                history: conversationHistory,
                sceneNavigationHistory,
                meta: {{
                    sceneId: gameState.currentSceneId || normalizeSceneId(scene?.scene_id),
                    speaker: getSceneSpeakerName(scene),
                    preview: summarizeSceneText(scene?.text || '')
                }}
            }};
        }}

        function handleSaveLoadPrimaryAction(slotIndex) {{
            if (saveLoadMode === 'save') {{
                saveToSlot(slotIndex);
                return;
            }}
            loadFromSlot(slotIndex);
        }}

        function saveToSlot(slotIndex) {{
            const existing = readSaveSlot(slotIndex);
            if (existing && !confirm(`${{getSaveSlotLabel(slotIndex)}} に上書き保存しますか？`)) {{
                return;
            }}

            try {{
                const saved = safeStorageSet(getSaveSlotKey(slotIndex), JSON.stringify(buildSaveData()));
                if (!saved) {{
                    throw new Error('localStorage に保存できませんでした');
                }}
                renderSaveSlots();
                closeSaveLoadModal();
                alert(`${{getSaveSlotLabel(slotIndex)}} にセーブしました!`);
            }} catch (e) {{
                alert('セーブに失敗しました: ' + e.message);
            }}
        }}

        function loadFromSlot(slotIndex) {{
            try {{
                const data = readSaveSlot(slotIndex);
                if (!data) {{
                    alert('セーブデータがありません');
                    return;
                }}

                const nextSceneIndex = Number.parseInt(data.sceneIndex, 10);
                currentSceneIndex = Number.isInteger(nextSceneIndex) && nextSceneIndex >= 0 && nextSceneIndex < SCENARIO_DATA.length
                    ? nextSceneIndex
                    : 0;

                const loadedState = data.state && typeof data.state === 'object' ? data.state : {{}};
                gameState = {{
                    ...createInitialGameState(),
                    ...loadedState,
                    visitedScenes: Array.isArray(loadedState.visitedScenes) ? loadedState.visitedScenes : [],
                    choices: loadedState.choices && typeof loadedState.choices === 'object' ? loadedState.choices : {{}},
                    settings: {{ ...DEFAULT_SETTINGS, ...(loadedState.settings || {{}}) }}
                }};
                conversationHistory = Array.isArray(data.history)
                    ? data.history.map(entry => normalizeConversationHistoryEntry(entry))
                    : [];
                const loadedSceneNavigationHistory = Array.isArray(data.sceneNavigationHistory)
                    ? data.sceneNavigationHistory.map(normalizeSceneNavigationEntry).filter(Boolean)
                    : [];
                sceneNavigationHistory = loadedSceneNavigationHistory.length
                    ? loadedSceneNavigationHistory
                    : [{{
                        sceneIndex: currentSceneIndex,
                        historyLengthBefore: Math.max(conversationHistory.length - 1, 0)
                    }}];

                closeSaveLoadModal();
                showScreen('game-screen');
                loadScene(currentSceneIndex, {{ recordHistory: false }});
            }} catch (e) {{
                alert('ロードに失敗しました: ' + e.message);
            }}
        }}

        function deleteSaveSlot(slotIndex) {{
            if (!readSaveSlot(slotIndex)) {{
                return;
            }}
            if (!confirm(`${{getSaveSlotLabel(slotIndex)}} のセーブデータを破棄しますか？`)) {{
                return;
            }}
            safeStorageRemove(getSaveSlotKey(slotIndex));
            renderSaveSlots();
            alert(`${{getSaveSlotLabel(slotIndex)}} のセーブデータを破棄しました。`);
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

        function parsePositiveInt(value, fallback) {{
            const parsed = Number.parseInt(value, 10);
            return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
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
            document.getElementById('auto-scene-change-delay').value = parsePositiveInt(
                gameState.settings.autoSceneChangeDelay,
                AUTO_SCENE_CHANGE_DELAY
            );
            document.getElementById('bgm-volume').value = gameState.settings.bgmVolume;
            document.getElementById('se-volume').value = gameState.settings.seVolume;
            syncCustomNameInputs(gameState.settings.customName);
            if (bgmAudio) {{
                bgmAudio.volume = getBgmTargetVolume();
            }}
        }}
        
        function saveSettings() {{
            gameState.settings.textSpeed = parseInt(document.getElementById('text-speed').value);
            gameState.settings.autoSceneChangeDelay = parsePositiveInt(
                document.getElementById('auto-scene-change-delay').value,
                AUTO_SCENE_CHANGE_DELAY
            );
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
            closeModalById('game-menu');
        }}
        
        function showSettings() {{
            document.getElementById('settings-screen').classList.remove('hidden');
            closeGameMenu();
        }}
        
        function closeSettings() {{
            if (!saveSettings()) return;
            closeModalById('settings-screen');
        }}
        
        function showCredits() {{
            document.getElementById('credits-screen').classList.remove('hidden');
        }}
        
        function closeCredits() {{
            closeModalById('credits-screen');
        }}
        
        function returnToTitle() {{
            activateTitleScreen();
            closeGameMenu();
            sceneNavigationHistory = [];
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
    
    parser = argparse.ArgumentParser(
        description="CSVファイルからビジュアルノベル形式のウェブゲームを生成します。"
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="scenario.csv",
        help="入力CSVファイル名（inputディレクトリ配下）"
    )
    parser.add_argument(
        "--replacement-html-only",
        action="store_true",
        help="assetsディレクトリを生成せず、差し替え用HTMLのみをoutput直下へ出力する"
    )
    args = parser.parse_args()

    input_dir = "input"
    output_dir = "output"
    csv_file = args.csv_file
    
    try:
        # ジェネレーターを初期化
        generator = LuminasScript(input_dir, output_dir)
        
        # CSVを読み込み
        generator.load_csv(csv_file)
        
        if args.replacement_html_only:
            output_path = generator.generate_replacement_html(csv_file)
        else:
            output_path = generator.generate_html(csv_file)
        
        print()
        print("=" * 60)
        print("  ✓ 生成完了!")
        print("=" * 60)
        print()
        if args.replacement_html_only:
            print(f"差し替え用HTML: {output_path}")
            print("このHTMLは既存の通常生成物へ差し替えて使用してください。")
        else:
            print(f"生成先ディレクトリ: {output_path}")
            print(f"HTML: {output_path / 'game.html'}")
            print(f"assets: {output_path / 'assets'}")
        print("ブラウザで開いてゲームをお楽しみください!")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

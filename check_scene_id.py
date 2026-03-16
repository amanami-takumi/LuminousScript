#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scene_id が luminas_script.py の想定フォーマットに沿っているかをチェックする。
"""

import argparse
import csv
import sys
from pathlib import Path
import re

ENCODINGS = [
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "shift-jis",
    "cp932",
]

SPECIAL_TYPES = {"T", "Q", "E"}
RESERVED_BRANCH = {"M", "Q", "T", "E"}
RE_DIGITS = re.compile(r"^\d+$")
RE_LETTER = re.compile(r"^[A-Z]$")


def read_csv_rows(csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    for encoding in ENCODINGS:
        try:
            with open(csv_path, "r", encoding=encoding) as f:
                sample = f.read(1024)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t ")
                    reader = csv.DictReader(f, dialect=dialect)
                except Exception:
                    reader = csv.DictReader(f)

                rows = list(reader)
                if rows and "scene_id" in rows[0]:
                    return rows, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            continue

    raise ValueError(f"CSVファイルのエンコーディングを検出できませんでした: {csv_path}")


def normalize_scene_id(scene_id: str) -> str:
    return (scene_id or "").strip()


def is_choice_scene(parts):
    if len(parts) >= 2 and (parts[1] in SPECIAL_TYPES or parts[-1] in SPECIAL_TYPES):
        return parts[1] == "Q" or parts[-1] == "Q"
    return False


def validate_scene_id(scene_id_raw, line_no, errors, warnings):
    scene_id = normalize_scene_id(scene_id_raw)
    if not scene_id:
        errors.append((line_no, scene_id_raw, "scene_id が空です"))
        return scene_id

    if scene_id_raw != scene_id:
        warnings.append((line_no, scene_id_raw, "前後に空白があります"))

    if " " in scene_id:
        warnings.append((line_no, scene_id_raw, "scene_id 内に空白があります"))
    if "‐" in scene_id:
        warnings.append((line_no, scene_id_raw, "scene_id の区切り文字は「-」です"))

    parts = scene_id.split("-")
    if any(p == "" for p in parts):
        errors.append((line_no, scene_id_raw, "ハイフンの連続または先頭/末尾ハイフンがあります"))
        return scene_id
    if len(parts) < 2:
        errors.append((line_no, scene_id_raw, "パーツ数が不足しています (例: 1-1)"))
        return scene_id


    chapter = parts[0]
    if not RE_DIGITS.match(chapter):
        errors.append((line_no, scene_id_raw, "先頭パーツ(章番号)が数字ではありません"))

    second = parts[1]
    last = parts[-1]

    if second in SPECIAL_TYPES:
        if len(parts) != 2:
            errors.append((line_no, scene_id_raw, "T/Q/E は 2 パーツ構成のみを想定しています (例: 1-T)"))
        return scene_id

    if RE_LETTER.match(second) and second not in RESERVED_BRANCH:
        if len(parts) < 3:
            errors.append((line_no, scene_id_raw, "分岐ルートは 3 パーツ以上が必要です (例: 1-A-1)"))
            return scene_id
        if not RE_DIGITS.match(parts[2]):
            errors.append((line_no, scene_id_raw, "分岐ルートの3番目は数字を想定しています (例: 1-A-1)"))
        if len(parts) > 3 and not all(RE_DIGITS.match(p) for p in parts[2:]):
            warnings.append((line_no, scene_id_raw, "分岐ルートの追加パーツは数字のみを推奨します"))
        return scene_id

    if RE_DIGITS.match(second):
        if len(parts) > 2 and not all(RE_DIGITS.match(p) for p in parts[1:]):
            warnings.append((line_no, scene_id_raw, "数値シーンの追加パーツは数字のみを推奨します"))
        return scene_id




def main():
    parser = argparse.ArgumentParser(description="scene_id の妥当性チェック")
    parser.add_argument("csv", nargs="?", default="scenario.csv", help="CSVファイル名 (input/配下)")
    parser.add_argument("--input-dir", default="input", help="入力ディレクトリ")
    args = parser.parse_args()

    csv_path = Path(args.input_dir) / args.csv

    try:
        rows, encoding = read_csv_rows(csv_path)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    if not rows:
        print("ERROR: CSVにデータ行がありません")
        return 1

    errors = []
    warnings = []
    entries = []
    seen = {}

    for idx, row in enumerate(rows):
        line_no = idx + 2  # header is line 1
        scene_id_raw = row.get("scene_id", "")
        scene_id = validate_scene_id(scene_id_raw, line_no, errors, warnings)
        text = row.get("text", "")
        entries.append({
            "line_no": line_no,
            "scene_id_raw": scene_id_raw,
            "scene_id": scene_id,
            "text": text,
        })

        if scene_id:
            if scene_id in seen:
                errors.append((line_no, scene_id_raw, f"scene_id が重複しています (既出: {seen[scene_id]})"))
            else:
                seen[scene_id] = f"line {line_no}"

    all_ids = set(seen.keys())

    # choice scene の分岐先チェック
    # for entry in entries:
    #     scene_id = entry["scene_id"]
    #     if not scene_id:
    #         continue
    #     parts = scene_id.split("-")
    #     if not is_choice_scene(parts):
    #         continue
    # 
    #     base_parts = parts[:-1]
    #     text = entry["text"] or ""
    #     choices = [c.strip() for c in str(text).splitlines() if c.strip()]
    #     for idx, _choice in enumerate(choices):
    #         branch_letter = chr(65 + idx)
    #         expected_id = "-".join(base_parts + [branch_letter, "1"])
    #         if expected_id not in all_ids:
    #             errors.append((entry["line_no"], entry["scene_id_raw"], f"分岐先が見つかりません: {expected_id}"))

    if warnings:
        print("WARNINGS:")
        for line_no, raw, msg in warnings:
            print(f"  line {line_no}: '{raw}' - {msg}")

    if errors:
        print("ERRORS:")
        for line_no, raw, msg in errors:
            print(f"  line {line_no}: '{raw}' - {msg}")
        return 1

    print(f"✓ scene_id チェック完了 (encoding: {encoding})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

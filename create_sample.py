#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
サンプルシナリオ生成スクリプト
LuminasScriptで使用できるサンプルCSVを生成します。
"""

import csv
from pathlib import Path


def create_sample_scenario():
    """サンプルシナリオCSVを作成"""
    
    # サンプルデータ
    scenario = [
        {
            'scene_id': '1-T',
            'person_name': '',
            'text': '第一章 新しい朝',
            'effect': '',
            'background_image': 'bg_1_morning_bed.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-1',
            'person_name': '天波たくみ',
            'text': 'おはよう！\nもー、今日もお寝坊さん？',
            'effect': '',
            'background_image': 'bg_1_morning_bed.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-2',
            'person_name': 'Astrolabe',
            'text': '別に寝てたっていいじゃん。\n学校があるわけでも、仕事があるわけでもないんだしさ',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': 'sp_astrolabe_jitome.png',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-Q',
            'person_name': '',
            'text': 'A 実は今日から学校に行くことになりました！\nB それもそうだね',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-A-1',
            'person_name': '天波たくみ',
            'text': '実は、伝えたいことがあって。\n今日からね。あなたは。',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-A-2',
            'person_name': 'Astrolabe',
            'text': 'ごくり。。.',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': 'sp_amanamitakumi_smile.png',
            'right_standing_portrait_image': 'sp_astrolabe_jitome.png',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-A-3',
            'person_name': '天波たくみ',
            'text': '学校に行くことになりました！',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': 'sp_amanamitakumi_smile.png',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-B-1',
            'person_name': '天波たくみ',
            'text': 'そりゃそうだ。\nでもさ、学校とか行ってみない？',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': 'sp_amanamitakumi_nigawarai.png',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-B-2',
            'person_name': 'Astrolabe',
            'text': 'めんどくさいなぁ',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': 'sp_amanamitakumi_ase.png',
            'right_standing_portrait_image': 'sp_astrolabe_jitome.png',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-B-3',
            'person_name': '天波たくみ',
            'text': 'そこをなんとか！\nというか、学校って楽しいところだよ？',
            'effect': '',
            'background_image': 'bg_myroom_1.png',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': 'sp_amanamitakumi_ase.png',
            'right_standing_portrait_image': 'sp_astrolabe_jitome.png',
            'sounds': '',
            'bgm': ''
        },
        {
            'scene_id': '1-E',
            'person_name': '',
            'text': '第一章 完',
            'effect': '',
            'background_image': '',
            'center_standing_portrait_image': '',
            'left_standing_portrait_image': '',
            'right_standing_portrait_image': '',
            'sounds': '',
            'bgm': ''
        }
    ]
    
    # CSVファイルに書き込み
    output_path = Path('input') / 'sample_scenario.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'scene_id', 'person_name', 'text', 'effect',
            'background_image', 'center_standing_portrait_image',
            'left_standing_portrait_image', 'right_standing_portrait_image',
            'sounds', 'bgm'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scenario)
    
    print(f"✓ サンプルシナリオを作成しました: {output_path}")
    print(f"  シーン数: {len(scenario)}")
    print()
    print("次のステップ:")
    print("1. input/assets/backgrounds/ に背景画像を配置")
    print("2. input/assets/characters/ にキャラクター画像を配置")
    print("3. python luminas_script.py sample_scenario.csv を実行")


if __name__ == "__main__":
    create_sample_scenario()

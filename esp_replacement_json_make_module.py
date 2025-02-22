
## esp_replacement_json_make_module.py(4つ目)

"""
エスペラント文字の変換や、ルビサイズ調整、置換処理用の関数などをまとめたモジュール。

【構成】
1) 文字変換用の辞書定義 (字上符形式への変換など)
2) 基本の文字形式変換関数 (replace_esperanto_chars, convert_to_circumflex, など)
3) 文字幅計測＆<br>挿入関数 (measure_text_width_Arial16, insert_br_at_half_width, insert_br_at_third_width)
4) 出力フォーマット (output_format) 関連
5) 文字列判定・placeholder インポートなどの補助関数
6) multiprocessing 関連の並列置換用関数 (process_chunk_for_pre_replacements, parallel_build_pre_replacements_dict)
"""

import re
import json
import multiprocessing
import pandas as pd
import os
from typing import List, Dict, Tuple, Optional

#=================================================================
# 1) エスペラント文字変換用の辞書 (同様のものが他のファイルにもある)
#=================================================================
x_to_circumflex = {'cx': 'ĉ', 'gx': 'ĝ', 'hx': 'ĥ', 'jx': 'ĵ', 'sx': 'ŝ', 'ux': 'ŭ',
                   'Cx': 'Ĉ', 'Gx': 'Ĝ', 'Hx': 'Ĥ', 'Jx': 'Ĵ', 'Sx': 'Ŝ', 'Ux': 'Ŭ'}
circumflex_to_x = {'ĉ': 'cx', 'ĝ': 'gx', 'ĥ': 'hx', 'ĵ': 'jx', 'ŝ': 'sx', 'ŭ': 'ux',
                   'Ĉ': 'Cx', 'Ĝ': 'Gx', 'Ĥ': 'Hx', 'Ĵ': 'Jx', 'Ŝ': 'Sx', 'Ŭ': 'Ux'}
x_to_hat = {'cx': 'c^', 'gx': 'g^', 'hx': 'h^', 'jx': 'j^', 'sx': 's^', 'ux': 'u^',
            'Cx': 'C^', 'Gx': 'G^', 'Hx': 'H^', 'Jx': 'J^', 'Sx': 'S^', 'Ux': 'U^'}
hat_to_x = {'c^': 'cx', 'g^': 'gx', 'h^': 'hx', 'j^': 'jx', 's^': 'sx', 'u^': 'ux',
            'C^': 'Cx', 'G^': 'Gx', 'H^': 'Hx', 'J^': 'Jx', 'S^': 'Sx', 'U^': 'Ux'}
hat_to_circumflex = {'c^': 'ĉ', 'g^': 'ĝ', 'h^': 'ĥ', 'j^': 'ĵ', 's^': 'ŝ', 'u^': 'ŭ',
                     'C^': 'Ĉ', 'G^': 'Ĝ', 'H^': 'Ĥ', 'J^': 'Ĵ', 'S^': 'Ŝ', 'U^': 'Ŭ'}
circumflex_to_hat = {'ĉ': 'c^', 'ĝ': 'g^', 'ĥ': 'h^', 'ĵ': 'j^', 'ŝ': 's^', 'ŭ': 'u^',
                     'Ĉ': 'C^', 'Ĝ': 'G^', 'Ĥ': 'H^', 'Ĵ': 'J^', 'Ŝ': 'S^', 'Ŭ': 'U^'}

#=================================================================
# 2) 基本の文字形式変換関数
#=================================================================
def replace_esperanto_chars(text, char_dict: Dict[str, str]) -> str:
    for original_char, converted_char in char_dict.items():
        text = text.replace(original_char, converted_char)
    return text

def convert_to_circumflex(text: str) -> str:
    # c^, g^... → ĉ, ĝ...  および cx, gx... → ĉ, ĝ... に変換
    text = replace_esperanto_chars(text, hat_to_circumflex)
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text

#=================================================================
# 3) 文字幅計測 & <br> 挿入関数
#=================================================================
def measure_text_width_Arial16(text, char_widths_dict: Dict[str, int]) -> int:
    """
    JSONで読み込んだ {文字: 幅(px)} の辞書を使い、
    text の合計幅を算出する
    """
    total_width = 0
    for ch in text:
        char_width = char_widths_dict.get(ch, 8)
        total_width += char_width
    return total_width

def insert_br_at_half_width(text, char_widths_dict: Dict[str, int]) -> str:
    """
    文字列幅が半分を超えたら <br> を入れる
    """
    total_width = measure_text_width_Arial16(text, char_widths_dict)
    half_width = total_width / 2

    current_width = 0
    insert_index = None
    for i, ch in enumerate(text):
        char_width = char_widths_dict.get(ch, 8)
        current_width += char_width
        if current_width >= half_width:
            insert_index = i + 1
            break

    if insert_index is not None:
        result = text[:insert_index] + "<br>" + text[insert_index:]
    else:
        result = text
    return result

def insert_br_at_third_width(text, char_widths_dict: Dict[str, int]) -> str:
    """
    文字列幅を三等分し、1/3 と 2/3 の位置に <br> を挿入する
    """
    total_width = measure_text_width_Arial16(text, char_widths_dict)
    third_width = total_width / 3
    thresholds = [third_width, third_width*2]

    current_width = 0
    insert_indices = []
    found_first = False
    for i, ch in enumerate(text):
        char_width = char_widths_dict.get(ch, 8)
        current_width += char_width
        if not found_first and current_width >= thresholds[0]:
            insert_indices.append(i+1)
            found_first = True
        elif found_first and current_width >= thresholds[1]:
            insert_indices.append(i+1)
            break

    result = text
    for idx in reversed(insert_indices):
        result = result[:idx] + "<br>" + result[idx:]
    return result

#=================================================================
# 4) 出力フォーマット (HTML/括弧形式等)
#=================================================================
def output_format(main_text, ruby_content, format_type, char_widths_dict):
    """
    エスペラント語根(main_text) と それに対応する訳/漢字(ruby_content) を
    指定の format_type で繋ぎ合わせる
    """
    if format_type == 'HTML格式_Ruby文字_大小调整':
        width_ruby = measure_text_width_Arial16(ruby_content, char_widths_dict)
        width_main = measure_text_width_Arial16(main_text, char_widths_dict)
        ratio_1 = width_ruby / width_main

        if ratio_1 > 6:
            return f'<ruby>{main_text}<rt class="XXXS_S">{insert_br_at_third_width(ruby_content, char_widths_dict)}</rt></ruby>'
        elif ratio_1 > (9/3):
            return f'<ruby>{main_text}<rt class="XXS_S">{insert_br_at_half_width(ruby_content, char_widths_dict)}</rt></ruby>'
        elif ratio_1 > (9/4):
            return f'<ruby>{main_text}<rt class="XS_S">{ruby_content}</rt></ruby>'
        elif ratio_1 > (9/5):
            return f'<ruby>{main_text}<rt class="S_S">{ruby_content}</rt></ruby>'
        elif ratio_1 > (9/6):
            return f'<ruby>{main_text}<rt class="M_M">{ruby_content}</rt></ruby>'
        elif ratio_1 > (9/7):
            return f'<ruby>{main_text}<rt class="L_L">{ruby_content}</rt></ruby>'
        elif ratio_1 > (9/8):
            return f'<ruby>{main_text}<rt class="XL_L">{ruby_content}</rt></ruby>'
        else:
            return f'<ruby>{main_text}<rt class="XXL_L">{ruby_content}</rt></ruby>'

    elif format_type == 'HTML格式_Ruby文字_大小调整_汉字替换':
        # main と ruby の立場を逆転したような形式
        width_ruby = measure_text_width_Arial16(ruby_content, char_widths_dict)
        width_main = measure_text_width_Arial16(main_text, char_widths_dict)
        ratio_2 = width_main / width_ruby
        if ratio_2 > 6:
            return f'<ruby>{ruby_content}<rt class="XXXS_S">{insert_br_at_third_width(main_text, char_widths_dict)}</rt></ruby>'
        elif ratio_2 > (9/3):
            return f'<ruby>{ruby_content}<rt class="XXS_S">{insert_br_at_half_width(main_text, char_widths_dict)}</rt></ruby>'
        elif ratio_2 > (9/4):
            return f'<ruby>{ruby_content}<rt class="XS_S">{main_text}</rt></ruby>'
        elif ratio_2 > (9/5):
            return f'<ruby>{ruby_content}<rt class="S_S">{main_text}</rt></ruby>'
        elif ratio_2 > (9/6):
            return f'<ruby>{ruby_content}<rt class="M_M">{main_text}</rt></ruby>'
        elif ratio_2 > (9/7):
            return f'<ruby>{ruby_content}<rt class="L_L">{main_text}</rt></ruby>'
        elif ratio_2 > (9/8):
            return f'<ruby>{ruby_content}<rt class="XL_L">{main_text}</rt></ruby>'
        else:
            return f'<ruby>{ruby_content}<rt class="XXL_L">{main_text}</rt></ruby>'

    elif format_type == 'HTML格式':
        return f'<ruby>{main_text}<rt>{ruby_content}</rt></ruby>'
    elif format_type == 'HTML格式_汉字替换':
        return f'<ruby>{ruby_content}<rt>{main_text}</rt></ruby>'
    elif format_type == '括弧(号)格式':
        return f'{main_text}({ruby_content})'
    elif format_type == '括弧(号)格式_汉字替换':
        return f'{ruby_content}({main_text})'
    elif format_type == '替换后文字列のみ(仅)保留(简单替换)':
        return f'{ruby_content}'

#=================================================================
# 5) 文字列判定・placeholder インポート等の補助関数
#=================================================================
def contains_digit(s: str) -> bool:
    return any(char.isdigit() for char in s)

def import_placeholders(filename: str) -> List[str]:
    with open(filename, 'r') as file:
        placeholders = [line.strip() for line in file if line.strip()]
    return placeholders

# 以下のパターンはHTMLルビを大文字化するためのもの(一部の拡張)
RUBY_PATTERN = re.compile(
    r'^'
    r'(.*?)'
    r'(<ruby>)'
    r'([^<]+)'
    r'(<rt[^>]*>)'
    r'([^<]*?(?:<br>[^<]*?){0,2})'
    r'(</rt>)'
    r'(</ruby>)?'
    r'(.*)'
    r'$'
)

def capitalize_ruby_and_rt(text: str) -> str:
    """
    <ruby>〜</ruby> の親文字列 / ルビ文字列を大文字化する例。
    """
    def replacer(match):
        g1 = match.group(1)
        g2 = match.group(2)
        g3 = match.group(3)
        g4 = match.group(4)
        g5 = match.group(5)
        g6 = match.group(6)
        g7 = match.group(7)
        g8 = match.group(8)
        if g1.strip():
            return g1.capitalize() + g2 + g3 + g4 + g5 + g6 + (g7 if g7 else '') + g8
        else:
            parent_text = g3.capitalize()
            rt_text = g5.capitalize()
            return g1 + g2 + parent_text + g4 + rt_text + g6 + (g7 if g7 else '') + g8

    replaced_text = RUBY_PATTERN.sub(replacer, text)
    if replaced_text == text:
        replaced_text = text.capitalize()
    return replaced_text

#=================================================================
# 6) multiprocessing 関連
#=================================================================
def safe_replace(text: str, replacements: List[Tuple[str, str, str]]) -> str:
    """
    こちらにも safe_replace が定義されている (同名関数)
    (mainページ用のesp_text_replacement_module.pyと重複しているが別ファイル)
    """
    valid_replacements = {}
    for old, new, placeholder in replacements:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements[placeholder] = new
    for placeholder, new in valid_replacements.items():
        text = text.replace(placeholder, new)
    return text

def process_chunk_for_pre_replacements(
    chunk: List[List[str]],
    replacements: List[Tuple[str, str, str]]
) -> Dict[str, List[str]]:
    """
    chunk: [[E_root, pos], ...] の部分リスト
    safe_replace による置換結果を { E_root: [replaced_stem, pos], ... } の形で返す
    """
    local_dict = {}
    for item in chunk:
        if len(item) != 2:
            continue
        E_root, pos_info = item
        if len(E_root) < 2:
            continue
        if E_root in local_dict:
            replaced_stem, existing_pos_str = local_dict[E_root]
            existing_pos_list = existing_pos_str.split(',')
            if pos_info not in existing_pos_list:
                existing_pos_list.append(pos_info)
                merged_pos_str = ",".join(existing_pos_list)
                local_dict[E_root] = [replaced_stem, merged_pos_str]
        else:
            replaced = safe_replace(E_root, replacements)
            local_dict[E_root] = [replaced, pos_info]
    return local_dict

def parallel_build_pre_replacements_dict(
    E_stem_with_Part_Of_Speech_list: List[List[str]],
    replacements: List[Tuple[str, str, str]],
    num_processes: int = 4
) -> Dict[str, List[str]]:
    """
    データを num_processes 個に分割し、process_chunk_for_pre_replacements を並列実行
    最終的に辞書をマージして返す。
    """
    total_len = len(E_stem_with_Part_Of_Speech_list)
    if total_len == 0:
        return {}

    chunk_size = -(-total_len // num_processes)
    chunks = []
    start_index = 0
    for _ in range(num_processes):
        end_index = min(start_index + chunk_size, total_len)
        chunk = E_stem_with_Part_Of_Speech_list[start_index:end_index]
        chunks.append(chunk)
        start_index = end_index
        if start_index >= total_len:
            break

    with multiprocessing.Pool(num_processes) as pool:
        partial_dicts = pool.starmap(
            process_chunk_for_pre_replacements,
            [(chunk, replacements) for chunk in chunks]
        )

    merged_dict = {}
    for partial_d in partial_dicts:
        for E_root, val in partial_d.items():
            replaced_stem, pos_str = val
            if E_root not in merged_dict:
                merged_dict[E_root] = [replaced_stem, pos_str]
            else:
                existing_replaced_stem, existing_pos_str = merged_dict[E_root]
                existing_pos_list = existing_pos_str.split(',')
                new_pos_list = pos_str.split(',')
                pos_merged = list(set(existing_pos_list) | set(new_pos_list))
                pos_merged_str = ",".join(sorted(pos_merged))
                merged_dict[E_root] = [existing_replaced_stem, pos_merged_str]

    return merged_dict

#=================================================================
# 追加(202502):
# 同一ルビが (ルビ付けした結果) 重複している場合に削除する関数
#=================================================================
IDENTICAL_RUBY_PATTERN = re.compile(r'<ruby>([^<]+)<rt class="XXL_L">([^<]+)</rt></ruby>')

def remove_redundant_ruby_if_identical(text: str) -> str:
    """
    <ruby>xxx<rt class="XXL_L">xxx</rt></ruby> のように、
    親文字列とルビ文字列が完全に同一の場合に <ruby> を取り除く
    """
    def replacer(match: re.Match) -> str:
        group1 = match.group(1)
        group2 = match.group(2)
        if group1 == group2:
            return group1
        else:
            return match.group(0)

    replaced_text = IDENTICAL_RUBY_PATTERN.sub(replacer, text)
    return replaced_text

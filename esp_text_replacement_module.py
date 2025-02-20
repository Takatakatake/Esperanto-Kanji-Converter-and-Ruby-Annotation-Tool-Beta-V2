
## esp_text_replacement_module.py(3つ目)

"""
このモジュールは「エスペラント文章の文字列(漢字)置換」を包括的に扱うツール集です。
主な機能：
1. エスペラント独自の文字形式（ĉ, ĝなど）への変換 → convert_to_circumflex
2. 特殊な半角スペースの統一（ASCIIスペースに） → unify_halfwidth_spaces
3. (現在不要になった) HTMLルビ付与関数 → wrap_text_with_ruby (コメントのみ)
4. %や@で囲まれたテキストのスキップ・局所変換 → (create_replacements_list_for_...)
5. 大域的なプレースホルダー置換 → safe_replace
6. それらをまとめて実行する複合置換関数 → orchestrate_comprehensive_esperanto_text_replacement
7. multiprocessing を用いた行単位の並列実行 → parallel_process / process_segment
"""

import re
import json
from typing import List, Tuple, Dict
import multiprocessing

# ================================
# 1) エスペラント文字変換用の辞書
# ================================
# それぞれ (x表記 → ĉ) や (ĉ → c^)など、様々なマッピングを辞書にしている
x_to_circumflex = {
    'cx': 'ĉ', 'gx': 'ĝ', 'hx': 'ĥ', 'jx': 'ĵ', 'sx': 'ŝ', 'ux': 'ŭ',
    'Cx': 'Ĉ', 'Gx': 'Ĝ', 'Hx': 'Ĥ', 'Jx': 'Ĵ', 'Sx': 'Ŝ', 'Ux': 'Ŭ'
}
circumflex_to_x = {
    'ĉ': 'cx', 'ĝ': 'gx', 'ĥ': 'hx', 'ĵ': 'jx', 'ŝ': 'sx', 'ŭ': 'ux',
    'Ĉ': 'Cx', 'Ĝ': 'Gx', 'Ĥ': 'Hx', 'Ĵ': 'Jx', 'Ŝ': 'Sx', 'Ŭ': 'Ux'
}
x_to_hat = {
    'cx': 'c^', 'gx': 'g^', 'hx': 'h^', 'jx': 'j^', 'sx': 's^', 'ux': 'u^',
    'Cx': 'C^', 'Gx': 'G^', 'Hx': 'H^', 'Jx': 'J^', 'Sx': 'S^', 'Ux': 'U^'
}
hat_to_x = {
    'c^': 'cx', 'g^': 'gx', 'h^': 'hx', 'j^': 'jx', 's^': 'sx', 'u^': 'ux',
    'C^': 'Cx', 'G^': 'Gx', 'H^': 'Hx', 'J^': 'Jx', 'S^': 'Sx', 'U^': 'Ux'
}
hat_to_circumflex = {
    'c^': 'ĉ', 'g^': 'ĝ', 'h^': 'ĥ', 'j^': 'ĵ', 's^': 'ŝ', 'u^': 'ŭ',
    'C^': 'Ĉ', 'G^': 'Ĝ', 'H^': 'Ĥ', 'J^': 'Ĵ', 'S^': 'Ŝ', 'U^': 'Ŭ'
}
circumflex_to_hat = {
    'ĉ': 'c^', 'ĝ': 'g^', 'ĥ': 'h^', 'ĵ': 'j^', 'ŝ': 's^', 'ŭ': 'u^',
    'Ĉ': 'C^', 'Ĝ': 'G^', 'Ĥ': 'H^', 'Ĵ': 'J^', 'Ŝ': 'S^', 'Ŭ': 'U^'
}

# ================================
# 2) 基本の文字形式変換関数
# ================================
def replace_esperanto_chars(text, char_dict: Dict[str, str]) -> str:
    # char_dict に含まれるペア (original_char, converted_char) ごとに
    # text.replace() していく
    for original_char, converted_char in char_dict.items():
        text = text.replace(original_char, converted_char)
    return text

def convert_to_circumflex(text: str) -> str:
    """
    テキストを字上符形式（ĉ, ĝ, ĥ, ĵ, ŝ, ŭなど）に統一します。
    1. hat_to_circumflex: c^ → ĉ
    2. x_to_circumflex: cx → ĉ
    """
    text = replace_esperanto_chars(text, hat_to_circumflex)
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text

def unify_halfwidth_spaces(text: str) -> str:
    """
    全角スペース(U+3000)は変更せず、半角スペースと視覚的に区別がつきにくい空白文字を
    ASCII半角スペース(U+0020)に統一する。
    """
    pattern = r"[\u00A0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A]"
    return re.sub(pattern, " ", text)

# ================================
# 3) (HTMLルビタグの補助関数) 
#  (現状不要とされている)
# ================================

# ================================
# 4) 占位符(placeholder)関連
# ================================
def safe_replace(text: str, replacements: List[Tuple[str, str, str]]) -> str:
    """
    (old, new, placeholder) のリストを受け取り、
    text中の old → placeholder → new の段階置換を行う。
    """
    valid_replacements = {}

    # まず old→placeholder
    for old, new, placeholder in replacements:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements[placeholder] = new

    # 次に placeholder→new
    for placeholder, new in valid_replacements.items():
        text = text.replace(placeholder, new)

    return text

def import_placeholders(filename: str) -> List[str]:
    """
    プレースホルダを行単位で読み込むだけの関数
    """
    with open(filename, 'r') as file:
        placeholders = [line.strip() for line in file if line.strip()]
    return placeholders

# '%' で囲まれた箇所をスキップするための正規表現
PERCENT_PATTERN = re.compile(r'%(.{1,50}?)%')
def find_percent_enclosed_strings_for_skipping_replacement(text: str) -> List[str]:
    """'%foo%' の形を全て抽出。50文字以内に限定。"""
    matches = []
    used_indices = set()
    for match in PERCENT_PATTERN.finditer(text):
        start, end = match.span()
        if start not in used_indices and end-2 not in used_indices:
            matches.append(match.group(1))
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_intact_parts(text: str, placeholders: List[str]) -> List[Tuple[str, str]]:
    """
    '%xxx%' で囲まれた箇所を検出し、
    ( '%xxx%', placeholder ) という形で対応させるリストを作る
    """
    matches = find_percent_enclosed_strings_for_skipping_replacement(text)
    replacements_list_for_intact_parts = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            replacements_list_for_intact_parts.append([f"%{match}%", placeholders[i]])
        else:
            break
    return replacements_list_for_intact_parts

# '@' で囲まれた箇所を局所置換するための正規表現
AT_PATTERN = re.compile(r'@(.{1,18}?)@')
def find_at_enclosed_strings_for_localized_replacement(text: str) -> List[str]:
    """'@foo@' の形を全て抽出。18文字以内に限定。"""
    matches = []
    used_indices = set()
    for match in AT_PATTERN.finditer(text):
        start, end = match.span()
        if start not in used_indices and end-2 not in used_indices:
            matches.append(match.group(1))
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_localized_replacement(text, placeholders: List[str],
                                                       replacements_list_for_localized_string: List[Tuple[str, str, str]]
                                                       ) -> List[List[str]]:
    """
    '@xxx@' で囲まれた箇所を検出し、
    その内部文字列 'xxx' を replacements_list_for_localized_string で置換した結果を
    placeholder に置き換える。
    """
    matches = find_at_enclosed_strings_for_localized_replacement(text)
    tmp_list = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            replaced_match = safe_replace(match, replacements_list_for_localized_string)
            tmp_list.append([f"@{match}@", placeholders[i], replaced_match])
        else:
            break
    return tmp_list

# ================================
# 5) メインの複合文字列(漢字)置換関数
# ================================
def orchestrate_comprehensive_esperanto_text_replacement(
    text, 
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    複数の変換ルールに従ってエスペラント文を文字列(漢字)置換するメイン関数。

    1) 空白の正規化 → 2) エスペラント文字(ĉ等)の字上符形式統一
    3) %で囲まれた部分をスキップ
    4) @で囲まれた部分を局所置換
    5) 大域置換
    6) 2文字語根の置換を2回
    7) プレースホルダ復元
    8) HTML形式が指定なら追加整形
    """
    # 1, 2) 空白の正規化 + エスペラント字上符への変換
    text = unify_halfwidth_spaces(text)
    text = convert_to_circumflex(text)

    # 3) %...% スキップ部の一時置換
    replacements_list_for_intact_parts = create_replacements_list_for_intact_parts(text, placeholders_for_skipping_replacements)
    # 文字数長い順にsort (衝突を避けるため)
    sorted_replacements_list_for_intact_parts = sorted(replacements_list_for_intact_parts, key=lambda x: len(x[0]), reverse=True)
    for original, place_holder_ in sorted_replacements_list_for_intact_parts:
        text = text.replace(original, place_holder_)

    # 4) @...@ 局所置換
    tmp_replacements_list_for_localized_string_2 = create_replacements_list_for_localized_replacement(
        text, placeholders_for_localized_replacement, replacements_list_for_localized_string
    )
    sorted_replacements_list_for_localized_string = sorted(tmp_replacements_list_for_localized_string_2, key=lambda x: len(x[0]), reverse=True)
    for original, place_holder_, replaced_original in sorted_replacements_list_for_localized_string:
        text = text.replace(original, place_holder_)

    # 5) 大域置換 (old, new, placeholder)
    valid_replacements = {}
    for old, new, placeholder in replacements_final_list:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements[placeholder] = new

    # 6) 2文字語根置換(2回)
    valid_replacements_for_2char_roots = {}
    for old, new, placeholder in replacements_list_for_2char:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements_for_2char_roots[placeholder] = new

    valid_replacements_for_2char_roots_2 = {}
    for old, new, placeholder in replacements_list_for_2char:
        if old in text:
            place_holder_second = "!" + placeholder + "!"
            text = text.replace(old, place_holder_second)
            valid_replacements_for_2char_roots_2[place_holder_second] = new

    # 7) placeholderを最終的な文字列に戻す
    for place_holder_second, new in reversed(valid_replacements_for_2char_roots_2.items()):
        text = text.replace(place_holder_second, new)

    for placeholder, new in reversed(valid_replacements_for_2char_roots.items()):
        text = text.replace(placeholder, new)

    for placeholder, new in valid_replacements.items():
        text = text.replace(placeholder, new)

    # 局所(@)・スキップ(%) の復元
    for original, place_holder_, replaced_original in sorted_replacements_list_for_localized_string:
        text = text.replace(place_holder_, replaced_original.replace("@",""))
    for original, place_holder_ in sorted_replacements_list_for_intact_parts:
        text = text.replace(place_holder_, original.replace("%",""))

    # 8) HTML形式であれば、改行を <br> に変換 + スペースを &nbsp; に置換
    if "HTML" in format_type:
        text = text.replace("\n", "<br>\n")
        # text = wrap_text_with_ruby(text, chunk_size=10) # (過去の関数/不要)
        text = re.sub(r"   ", "&nbsp;&nbsp;&nbsp;", text)  # 3つ以上の空白を変換
        text = re.sub(r"  ", "&nbsp;&nbsp;", text)  # 2つ以上の空白を変換

    return text

# ================================
# 6) multiprocessing 関連
# ================================

def process_segment(
    lines: List[str],
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    multiprocessing用の下請け関数。
    lines (文字列リスト) を結合してから orchestrate_comprehensive_esperanto_text_replacement を実行。
    """
    segment = ''.join(lines)
    result = orchestrate_comprehensive_esperanto_text_replacement(
        segment,
        placeholders_for_skipping_replacements,
        replacements_list_for_localized_string,
        placeholders_for_localized_replacement,
        replacements_final_list,
        replacements_list_for_2char,
        format_type
    )
    return result


def parallel_process(
    text: str,
    num_processes: int,
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    与えられた text を行単位で分割し、process_segment を
    マルチプロセスで並列実行した結果を結合する。
    """
    if num_processes <= 1:
        # シングルコアで直接orchestrate_comprehensive_esperanto_text_replacementを呼ぶ
        return orchestrate_comprehensive_esperanto_text_replacement(
            text,
            placeholders_for_skipping_replacements,
            replacements_list_for_localized_string,
            placeholders_for_localized_replacement,
            replacements_final_list,
            replacements_list_for_2char,
            format_type
        )

    # 行ごとに分割 (改行込み)
    lines = re.findall(r'.*?\n|.+$', text)
    num_lines = len(lines)
    if num_lines <= 1:
        # 行数が1以下なら並列化しても意味ないのでシングルで
        return orchestrate_comprehensive_esperanto_text_replacement(
            text,
            placeholders_for_skipping_replacements,
            replacements_list_for_localized_string,
            placeholders_for_localized_replacement,
            replacements_final_list,
            replacements_list_for_2char,
            format_type
        )

    lines_per_process = max(num_lines // num_processes, 1)
    ranges = [(i * lines_per_process, (i + 1) * lines_per_process) for i in range(num_processes)]
    # 最後のプロセスに残りを全部割り当てる
    ranges[-1] = (ranges[-1][0], num_lines)

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.starmap(
            process_segment,
            [
                (
                    lines[start:end],
                    placeholders_for_skipping_replacements,
                    replacements_list_for_localized_string,
                    placeholders_for_localized_replacement,
                    replacements_final_list,
                    replacements_list_for_2char,
                    format_type
                )
                for (start, end) in ranges
            ]
        )
    return ''.join(results)


def apply_ruby_html_header_and_footer(processed_text: str, format_type: str) -> str:
    """
    指定された出力形式に応じて、processed_text に対するHTMLヘッダーとフッターを適用する。
    例: ルビサイズ調整用の<style> を挿入するなど。
    """
    if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换'):
        # html形式におけるルビサイズの変更形式
        ruby_style_head="""<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>大多数の环境中で正常に运行するRuby显示功能</title>
    <style>

    html, body {
      -webkit-text-size-adjust: 100%;
      -moz-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      text-size-adjust: 100%;
    }

  
      :root {
        --ruby-color: blue;
        --ruby-font-size: 0.5em;
      }
      html {
        font-size: 100%; /* 多くのブラウザは16px相当が標準 */
      }

      .text-M_M {
        font-size: 1rem!important; 
        font-family: Arial, sans-serif;
        line-height: 2.0 !important;  /* text-M_Mのline-heightとrubyのline-heightは一致させる必要がある。 */
        display: block; /* ブロック要素として扱う */
        position: relative;
      }
  
      /* ▼ ルビ（フレックスでルビを上に表示） */
      ruby {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        vertical-align: top !important;
        line-height: 2.0 !important;
        margin: 0 !important;
        padding: 0 !important;
        font-size: 1rem !important;
      }
  
      /* ▼ 追加マイナス余白（ルビサイズ別に上書き） */
      rt {
        display: block !important;
        font-size: var(--ruby-font-size);
        color: var(--ruby-color);
        line-height: 1.05;/*ルビを改行するケースにおけるルビの行間*/
        text-align: center;
        /* margin-top: 0.2em !important;   
        transform: translateY(0.4em) !important; */
      }
      rt.XXXS_S {
        --ruby-font-size: 0.3em;
        margin-top: -8.3em !important;/* ルビの高さ位置はここで調節する。 */
        transform: translateY(-0em) !important;
      }    
      rt.XXS_S {
        --ruby-font-size: 0.3em;
        margin-top: -7.2em !important;/* ルビの高さ位置はここで調節する。 */
        transform: translateY(-0em) !important;
      }
      rt.XS_S {
        --ruby-font-size: 0.3em;
        margin-top: -6.1em !important;
        transform: translateY(-0em) !important;
      }
      rt.S_S {
        --ruby-font-size: 0.4em;
        margin-top: -4.85em !important;
        transform: translateY(-0em) !important;
      }
      rt.M_M {
        --ruby-font-size: 0.5em;
        margin-top: -4.00em !important;
        transform: translateY(-0.0em) !important;
      }
      rt.L_L {
        --ruby-font-size: 0.6em; 
        margin-top: -3.55em !important;
        transform: translateY(-0.0em) !important;
      }
      rt.XL_L {
        --ruby-font-size: 0.7em;
        margin-top: -3.20em !important;
        transform: translateY(-0.0em) !important;
      }
      rt.XXL_L {
        --ruby-font-size: 0.8em;
        margin-top: -2.80em !important;
        transform: translateY(-0.0em) !important;
      }
  
    </style>
  </head>
  <body>
  <p class="text-M_M">
"""
        ruby_style_tail = "</p></body></html>"
    elif format_type in ('HTML格式','HTML格式_汉字替换'):
        ruby_style_head = """<style>
ruby rt {
    color: blue;
}
</style>
"""
        ruby_style_tail = "<br>"
    else:
        ruby_style_head = ""
        ruby_style_tail = ""
    
    return ruby_style_head + processed_text + ruby_style_tail
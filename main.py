import streamlit as st
import re
import io
from PIL import Image
import pandas as pd
import json

# 字上符付き文字の表記形式変換用の辞書型配列
x_to_circumflex = {'cx': 'ĉ', 'gx': 'ĝ', 'hx': 'ĥ', 'jx': 'ĵ', 'sx': 'ŝ', 'ux': 'ŭ','Cx': 'Ĉ', 'Gx': 'Ĝ', 'Hx': 'Ĥ', 'Jx': 'Ĵ', 'Sx': 'Ŝ', 'Ux': 'Ŭ'}
circumflex_to_x = {'ĉ': 'cx', 'ĝ': 'gx', 'ĥ': 'hx', 'ĵ': 'jx', 'ŝ': 'sx', 'ŭ': 'ux','Ĉ': 'Cx', 'Ĝ': 'Gx', 'Ĥ': 'Hx', 'Ĵ': 'Jx', 'Ŝ': 'Sx', 'Ŭ': 'Ux'}
x_to_hat = {'cx': 'c^', 'gx': 'g^', 'hx': 'h^', 'jx': 'j^', 'sx': 's^', 'ux': 'u^','Cx': 'C^', 'Gx': 'G^', 'Hx': 'H^', 'Jx': 'J^', 'Sx': 'S^', 'Ux': 'U^'}
hat_to_x = {'c^': 'cx', 'g^': 'gx', 'h^': 'hx', 'j^': 'jx', 's^': 'sx', 'u^': 'ux','C^': 'Cx', 'G^': 'Gx', 'H^': 'Hx', 'J^': 'Jx', 'S^': 'Sx', 'U^': 'Ux'}
hat_to_circumflex = {'c^': 'ĉ', 'g^': 'ĝ', 'h^': 'ĥ', 'j^': 'ĵ', 's^': 'ŝ', 'u^': 'ŭ','C^': 'Ĉ', 'G^': 'Ĝ', 'H^': 'Ĥ', 'J^': 'Ĵ', 'S^': 'Ŝ', 'U^': 'Ŭ'}
circumflex_to_hat = {'ĉ': 'c^', 'ĝ': 'g^', 'ĥ': 'h^', 'ĵ': 'j^', 'ŝ': 's^', 'ŭ': 'u^','Ĉ': 'C^', 'Ĝ': 'G^', 'Ĥ': 'H^', 'Ĵ': 'J^', 'Ŝ': 'S^', 'Ŭ': 'U^'}

# 字上符付き文字の表記形式変換用の関数
def replace_esperanto_chars(text,letter_dictionary):
    for esperanto_char, x_char in letter_dictionary.items():
        text = text.replace(esperanto_char, x_char)
    return text

def unify_halfwidth_spaces(text):
    """全角スペース(U+3000)は変更せず、半角スペースと視覚的に区別がつきにくい空白文字を
        ASCII半角スペース(U+0020)に統一する。連続した空白は1文字ずつ置換する。"""
    pattern = r"[\u00A0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A]"# 対象とする空白文字をまとめたパターン
    return re.sub(pattern, " ", text)# マッチした部分を半角スペースに置換

# 置換に用いる関数。正規表現、C++など様々な形式の置換を試したが、pythonでplaceholder(占位符)を用いる形式の置換が、最も処理が高速であった。(しかも大変シンプルでわかりやすい。)
def safe_replace(text, replacements):
    valid_replacements = {}
    # 置換対象(old)をplaceholderに一時的に置換
    for old, new, placeholder in replacements:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements[placeholder] = new# 後で置換後の文字列(new)に置換し直す必要があるplaceholderを辞書(valid_replacements)に記録しておく。
    # placeholderを置換後の文字列(new)に置換)
    for placeholder, new in valid_replacements.items():
        text = text.replace(placeholder, new)
    return text

# プレースホルダーを用いた文字列(漢字)置換関数
def enhanced_safe_replace_func_expanded_for_2char_roots(text, replacements, replacements_list_for_2char):
    valid_replacements = {}
    for old, new, placeholder in replacements:
        if old in text:
            text = text.replace(old, placeholder)# 置換前の文字列を一旦プレースホルダーに置き換える。
            valid_replacements[placeholder] = new
# ここで、2文字の語根の文字列(漢字)置換を実施することとした(202412の変更)。  &%
    valid_replacements_for_2char_roots = {}
    for old, new, placeholder in replacements_list_for_2char:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements_for_2char_roots[placeholder] = new
    valid_replacements_for_2char_roots_2 = {}
    for old, new, placeholder in replacements_list_for_2char:
        if old in text:
            place_holder_second="!"+placeholder+"!"# 2回目のplace_holderは少し変更を加えたほうが良いはず。
            text = text.replace(old, place_holder_second)
            valid_replacements_for_2char_roots_2[place_holder_second] = new
    for place_holder_second, new in reversed(valid_replacements_for_2char_roots_2.items()):# ここで、reverseにすることがポイント。
        text = text.replace(place_holder_second, new)# プレースホルダーを置換後の文字列に置き換える。
    for placeholder, new in reversed(valid_replacements_for_2char_roots.items()):
        text = text.replace(placeholder, new)# プレースホルダーを置換後の文字列に置き換える。
    for placeholder, new in valid_replacements.items():
        text = text.replace(placeholder, new)
    return text


# '%'で囲まれた50文字以内の部分を同定し、文字列(漢字)置換せずにそのまま保存しておくための関数群
def find_strings_in_text(text):
    # 正規表現パターンを定義
    pattern = re.compile(r'%(.{1,50}?)%')# re.DOTALLで、任意の文字列に"改行"も含むようにできる。(今はしない。)
    matches = []
    used_indices = set()

    # 正規表現のマッチを見つける
    for match in pattern.finditer(text):
        start, end = match.span()
        # 重複する%を避けるためにインデックスをチェック
        if start not in used_indices and end-2 not in used_indices:  # end-2 because of double %
            matches.append(match.group(1))
            # インデックスを使用済みセットに追加
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_intact_parts(text, placeholders):
    # テキストから%で囲まれた部分を抽出
    matches = find_strings_in_text(text)
    replacements_list_for_intact_parts = []
    # プレースホルダーとマッチを対応させる
    for i, match in enumerate(matches):
        if i < len(placeholders):
            replacements_list_for_intact_parts.append([f"%{match}%", placeholders[i]])
        else:
            break  # プレースホルダーが足りなくなった場合は終了
    return replacements_list_for_intact_parts

def import_placeholders(filename):# placeholder(占位符)をインポートするためだけの関数
    with open(filename, 'r') as file:
        placeholders = [line.strip() for line in file if line.strip()]
    return placeholders

# '@'で囲まれた18文字(PEJVOに収録されている最長語根の文字数)以内の部分を同定し、局所的な文字列(漢字)置換を実行するための関数群
def find_strings_in_text_for_localized_replacement(text):
    # 正規表現パターンを定義
    pattern = re.compile(r'@(.{1,18}?)@')# re.DOTALLで、任意の文字列に"改行"も含むようにできる。(今はしない。)
    matches = []
    used_indices = set()

    # 正規表現のマッチを見つける
    for match in pattern.finditer(text):
        start, end = match.span()
        # 重複する@を避けるためにインデックスをチェック
        if start not in used_indices and end-2 not in used_indices:  # end-2 because of double @
            matches.append(match.group(1))
            # インデックスを使用済みセットに追加
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_localized_replacement(text, placeholders, replacements_list_for_localized_string):
    # テキストから@で囲まれた部分を抽出
    matches = find_strings_in_text_for_localized_replacement(text)
    tmp_replacements_list_for_localized_string = []
    # プレースホルダーとマッチを対応させる
    for i, match in enumerate(matches):
        if i < len(placeholders):
            replaced_match=safe_replace(match, replacements_list_for_localized_string)# ここで、まず１つplaceholdersが要る。
            # print(match,replaced_match)
            tmp_replacements_list_for_localized_string.append([f"@{match}@", placeholders[i],replaced_match])# ここに、置換後の
        else:
            break  # プレースホルダーが足りなくなった場合は終了
    return tmp_replacements_list_for_localized_string

placeholders_for_skipping_replacements = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt')
placeholders_for_localized_replacement = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt')

st.title("エスペラント文を漢字置換したり、HTML形式の訳ルビを振ったりする")

# ユーザーに見せる選択肢(韓国語)→これを日本語表記に変更
options = {
    'HTML形式＿ルビ文字のサイズ調整': 'HTML格式_Ruby文字_大小调整',
    'HTML形式＿ルビ文字のサイズ調整(漢字置換)': 'HTML格式_Ruby文字_大小调整_汉字替换',
    'HTML形式': 'HTML格式',
    'HTML形式(漢字置換)': 'HTML格式_汉字替换',
    '括弧形式': '括弧(号)格式',
    ' 括弧形式(漢字置換)': '括弧(号)格式_汉字替换',
    '単純な置換': '替换后文字列のみ(仅)保留(简单替换)'
}

# ユーザーに見せる選択肢を日本語で表示
display_options = list(options.keys())
# Streamlit の selectbox を表示(韓国語部分→日本語へ)
selected_display = st.selectbox('出力形式を選択(置換用のJSONファイルを作成したときと同じ形式を選択):', display_options)

# 内部で使用する値を取得
format_type = options[selected_display]


selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)

replacements_final_list = None
replacements_list_for_localized_string = None
replacements_list_for_2char = None

if selected_option == "デフォルトを使用する":
    default_json_path = "./Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json"
    try:
        with open(default_json_path, 'r', encoding='utf-8') as g:
            combined_data = json.load(g)
            replacements_final_list = combined_data.get("全域替换用のリスト(列表)型配列(replacements_final_list)", None)
            replacements_list_for_localized_string = combined_data.get("局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", None)
            replacements_list_for_2char = combined_data.get("二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", None)
        st.success("デフォルトを使用します。")
    except Exception as e:
        st.error(f"JSONファイルの読み込みに失敗しました。: {e}")
        st.stop()
else:
    uploaded_file = st.file_uploader("JSONファイルをアップロードしてください。(合并3个JSON文件).json 形式)", type="json")
    if uploaded_file is not None:
        try:
            combined_data = json.load(uploaded_file)
            replacements_final_list = combined_data.get("全域替换用のリスト(列表)型配列(replacements_final_list)", None)
            replacements_list_for_localized_string = combined_data.get("局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", None)
            replacements_list_for_2char = combined_data.get("二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", None)
            st.success("JSONファイルのアップロードに成功しました。")
        except Exception as e:
            st.error(f"JSONファイルの読み込みに失敗しました。: {e}")
            st.stop()
    else:
        st.warning("有効なJSONファイルをアップロードするか、'デフォルトを使用する'を選択してください。")
        st.stop()

text1 = ""
with st.form(key='profile_form'):
    letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^ 形式'))
    text0 = st.text_area("エスペラントの文章")
    st.markdown("""「%」で前後を囲む(「%<50文字以内の文字列>%」形式)と、「%」で囲まれた部分は文字列(漢字)置換せず、元のまま保持することができます。""")
    st.markdown("""また、「@」で前後を囲む(「@<18文字以内の文字列>@」形式)と、「@」で囲まれた部分を局所的に文字列(漢字)置換します。""")

    submit_btn = st.form_submit_button('送信')
    cancel_btn = st.form_submit_button('キャンセル')
    if submit_btn:
        text1 = unify_halfwidth_spaces(text0)# 半角スペースと視覚的に区別がつきにくい特殊な空白文字を標準的なASCII半角スペース(U+0020)に置換する。 ただし、全角スペース(U+3000)は置換対象に含めていない。
        text1=replace_esperanto_chars(text1,hat_to_circumflex)
        text1=replace_esperanto_chars(text1,x_to_circumflex)

        replacements_list_for_intact_parts = create_replacements_list_for_intact_parts(text1, placeholders_for_skipping_replacements)
        sorted_replacements_list_for_intact_parts = sorted(replacements_list_for_intact_parts, key=lambda x: len(x[0]), reverse=True)
        for original, place_holder_ in sorted_replacements_list_for_intact_parts:
            text1 = text1.replace(original, place_holder_)

        tmp_replacements_list_for_localized_string_2 = create_replacements_list_for_localized_replacement(text1, placeholders_for_localized_replacement, replacements_list_for_localized_string)
        sorted_replacements_list_for_localized_string = sorted(tmp_replacements_list_for_localized_string_2, key=lambda x: len(x[0]), reverse=True)
        for original, place_holder_, replaced_original in sorted_replacements_list_for_localized_string:
            text1 = text1.replace(original, place_holder_)

        text1=enhanced_safe_replace_func_expanded_for_2char_roots(text1, replacements_final_list, replacements_list_for_2char)

        for original, place_holder_, replaced_original in sorted_replacements_list_for_localized_string:
            text1 = text1.replace(place_holder_, replaced_original.replace("@",""))

        for original, place_holder_ in sorted_replacements_list_for_intact_parts:
            text1 = text1.replace(place_holder_, original.replace("%",""))

        if letter_type == '上付き文字':
            text1 = replace_esperanto_chars(text1, x_to_circumflex)
        elif letter_type == '^ 形式':
            text1 = replace_esperanto_chars(text1, x_to_hat)
        
        if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换','HTML格式','HTML格式_汉字替换'):
            # 改行を <br> に変換
            text1 = text1.replace("\n", "<br>\n")
            # 連続する空白を &nbsp; に変換
            text1 = re.sub(r"   ", "&nbsp;&nbsp;&nbsp;", text1)  # 3つ以上の空白を変換
            text1 = re.sub(r"  ", "&nbsp;&nbsp;", text1)  # 2つ以上の空白を変換
        if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换'):
            # html形式におけるルビサイズの変更形式
            ruby_style_head="""<style>
        .text-S_S_S {font-size: 12px;}
        .text-M_M_M {font-size: 16px;}
        .text-L_L_L {font-size: 20px;}
        .text-X_X_X {font-size: 24px;}
        .ruby-XS_S_S { font-size: 0.30em; } /* Extra Small */
        .ruby-S_S_S  { font-size: 0.40em; } /* Small */
        .ruby-M_M_M  { font-size: 0.50em; } /* Medium */
        .ruby-L_L_L  { font-size: 0.60em; } /* Large */
        .ruby-XL_L_L { font-size: 0.70em; } /* Extra Large */
        .ruby-XXL_L_L { font-size: 0.80em; } /* Double Extra Large */

        ruby {
        display: inline-block;
        position: relative; /* 相対位置 */
        white-space: nowrap; /* 改行防止 */
        line-height: 1.9;
        }
        rt {
        position: absolute;
        top: -0.75em;
        left: 50%; /* 左端を親要素の中央に合わせる */
        transform: translateX(-50%); /* 中央に揃える */
        line-height: 2.1;
        color: blue; 
        }
        rt.ruby-XS_S_S { top: -0.20em; } /* ルビサイズに応じて、ルビを表示する高さを変える。 */
        rt.ruby-S_S_S  { top: -0.30em; }
        rt.ruby-M_M_M  { top: -0.40em; }
        rt.ruby-L_L_L  { top: -0.50em; }
        rt.ruby-XL_L_L { top: -0.65em; }
        rt.ruby-XXL_L_L{ top: -0.80em; }

        </style>
        <p class="text-M_M_M">
        """
            ruby_style_tail = "<br>\n</p>"

        elif format_type in ('HTML格式','HTML格式_汉字替换'):
            # ルビのスタイルは最小限
            ruby_style_head = """<style>
        ruby rt {
        color: blue;
        }
        </style>
        """
            ruby_style_tail="<br>"
        else:
            ruby_style_head=""
            ruby_style_tail=""

        text1=ruby_style_head+text1+ruby_style_tail
        st.text_area("文字列(漢字)置換後のテキストのプレビュー", text1, height=300)

if text1:
    to_download = io.BytesIO(text1.encode('utf-8'))
    to_download.seek(0)
    st.download_button(
        label="テキストをダウンロード",
        data=to_download,
        file_name="processed_text.html",
        mime="text/plain"
    )

st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")

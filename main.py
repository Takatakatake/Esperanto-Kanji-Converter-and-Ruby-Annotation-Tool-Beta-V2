##  main.py(1つ目)
# main.py (メインの Streamlit アプリ/機能拡充版202502)

import streamlit as st
import re
import io
import json
import pandas as pd  # 必要なら使う
from typing import List, Dict, Tuple, Optional
import streamlit.components.v1 as components
import multiprocessing

#=================================================================
# Streamlit で multiprocessing を使う際、PicklingError 回避のため
# 明示的に 'spawn' モードを設定する必要がある。
#=================================================================
try:
    multiprocessing.set_start_method("spawn")
except RuntimeError:
    pass  # すでに start method が設定済みの場合はここで無視する

#=================================================================
# エスペラント文の(漢字)置換・ルビ振りなどを行う独自モジュールから
# 関数をインポートする。
# esp_text_replacement_module.py内に定義されているツールをまとめて呼び出す
#=================================================================
from esp_text_replacement_module import (
    x_to_circumflex,
    x_to_hat,
    hat_to_circumflex,
    circumflex_to_hat,
    replace_esperanto_chars,
    import_placeholders,
    orchestrate_comprehensive_esperanto_text_replacement,
    parallel_process,
    apply_ruby_html_header_and_footer
)

#=================================================================
# Streamlit の @st.cache_data デコレータを使い、読み込み結果をキャッシュして
# JSONファイルのロード高速化を図る。大きなJSON(50MB程度)を都度読むと遅いので、
# ここで呼び出す関数をキャッシュする作り。
#=================================================================
@st.cache_data
def load_replacements_lists(json_path: str) -> Tuple[List, List, List]:
    """
    JSONファイルをロードし、以下の3つのリストをタプルとして返す:
    1) replacements_final_list
    2) replacements_list_for_localized_string
    3) replacements_list_for_2char
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    replacements_final_list = data.get(
        "全域替换用のリスト(列表)型配列(replacements_final_list)", []
    )
    replacements_list_for_localized_string = data.get(
        "局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", []
    )
    replacements_list_for_2char = data.get(
        "二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", []
    )
    return (
        replacements_final_list,
        replacements_list_for_localized_string,
        replacements_list_for_2char,
    )

#=================================================================
# Streamlit ページの見た目設定
# page_title: ブラウザタブに表示されるタイトル
# layout="wide" で横幅を広く使えるUIにする
#=================================================================
st.set_page_config(page_title="Esperanto文の文字列(漢字)置換ツール", layout="wide")

# タイトル部分
st.title("エスペラント文を漢字置換したり、HTML形式の訳ルビを振ったりする (拡張版)")
st.write("---")

#=================================================================
# 1) JSONファイル (置換ルール) をロード
#   (デフォルトを使うか、ユーザーがアップロードするかの選択)
#=================================================================
selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)

# Streamlit の折りたたみ (expander) でサンプルJSONのダウンロードを案内
with st.expander("**サンプルJSON(置換用JSONファイル)**"):
    # サンプルファイルのパス
    json_file_path = './Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json'
    # JSONファイルを読み込んでダウンロードボタンを生成
    with open(json_file_path, "rb") as file_json:
        btn_json = st.download_button(
            label="サンプルJSON(置換用JSONファイル)ダウンロード",
            data=file_json,
            file_name="置換用JSONファイル.json",
            mime="application/json"
        )

#=================================================================
# 置換ルールとして使うリスト3種を初期化しておく。
# (JSONファイル読み込み後に代入される)
#=================================================================
replacements_final_list: List[Tuple[str, str, str]] = []
replacements_list_for_localized_string: List[Tuple[str, str, str]] = []
replacements_list_for_2char: List[Tuple[str, str, str]] = []

# JSONファイルの読み込み方を分岐
if selected_option == "デフォルトを使用する":
    default_json_path = "./Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json"
    try:
        # デフォルトJSONをロード
        (replacements_final_list,
         replacements_list_for_localized_string,
         replacements_list_for_2char) = load_replacements_lists(default_json_path)
        st.success("デフォルトJSONの読み込みに成功しました。")
    except Exception as e:
        st.error(f"JSONファイルの読み込みに失敗: {e}")
        st.stop()
else:
    # ユーザーがファイルアップロードする場合
    uploaded_file = st.file_uploader("JSONファイルをアップロード (合并3个JSON文件).json 形式)", type="json")
    if uploaded_file is not None:
        try:
            combined_data = json.load(uploaded_file)
            replacements_final_list = combined_data.get(
                "全域替换用のリスト(列表)型配列(replacements_final_list)", [])
            replacements_list_for_localized_string = combined_data.get(
                "局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
            replacements_list_for_2char = combined_data.get(
                "二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
            st.success("アップロードしたJSONの読み込みに成功しました。")
        except Exception as e:
            st.error(f"アップロードJSONファイルの読み込みに失敗: {e}")
            st.stop()
    else:
        st.warning("JSONファイルがアップロードされていません。処理を停止します。")
        st.stop()

#=================================================================
# 2) placeholders (占位符) の読み込み
#    %...% や @...@ で囲った文字列を守るために使用する文字列群を読み込む
#=================================================================
placeholders_for_skipping_replacements: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)
placeholders_for_localized_replacement: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)

st.write("---")

#=================================================================
# 設定パラメータ (UI) - 高度な設定
# 並列処理 (multiprocessing) を利用できるかどうかのスイッチと、
# 同時プロセス数の選択
#=================================================================
st.header("高度な設定 (並列処理)")
with st.expander("並列処理についての設定を開く"):
    st.write("""
    ここでは、文字列(漢字)置換時に使用する並列処理のプロセス数を決めます。 
    """)
    use_parallel = st.checkbox("並列処理を使う", value=False)
    num_processes = st.number_input("同時プロセス数", min_value=2, max_value=4, value=4, step=1)

st.write("---")

#=================================================================
# 例: 出力形式の選択
# (HTMLルビ形式・括弧形式・文字列のみ など)
#=================================================================


# ユーザー向け選択肢（キー側を韓国語に変更 / 値側は機能維持のためそのまま）
options = {
    'HTML格式_Ruby文字_大小调整': 'HTML格式_Ruby文字_大小调整',
    'HTML格式_Ruby文字_大小调整_汉字替换': 'HTML格式_Ruby文字_大小调整_汉字替换',
    'HTML格式': 'HTML格式',
    'HTML格式_汉字替换': 'HTML格式_汉字替换',
    '括弧(号)格式': '括弧(号)格式',
    '括弧(号)格式_汉字替换': '括弧(号)格式_汉字替换',
    '替换后文字列のみ(仅)保留(简单替换)': '替换后文字列のみ(仅)保留(简单替换)'
}

# 사용자에게 보여줄 옵션 목록 (라벨)은 위의 dict 키들을 사용
display_options = list(options.keys())
selected_display = st.selectbox("出力形式を選択(置換用JSONファイルを作成したときと同じ形式を選択):", display_options)
format_type = options[selected_display]



# フォーム外で、変数 processed_text を初期化しておく
processed_text = ""

#=================================================================
# 4) 入力テキストのソースを選択 (手動入力 or ファイルアップロード)
#=================================================================
st.subheader("入力テキストのソース")
source_option = st.radio("入力テキストをどうしますか？", ("手動入力", "ファイルアップロード"))
uploaded_text = ""

# ファイルアップロードが選択された場合
if source_option == "ファイルアップロード":
    text_file = st.file_uploader("テキストファイルをアップロード (UTF-8)", type=["txt", "csv", "md"])
    if text_file is not None:
        uploaded_text = text_file.read().decode("utf-8", errors="replace")
        st.info("ファイルを読み込みました。")
    else:
        st.warning("テキストファイルがアップロードされていません。手動入力に切り替えるかファイルをアップロードしてください。")

#=================================================================
# フォーム: 実行ボタン(送信/キャンセル)を配置
#  - テキストエリアにエスペラント文を入力してもらう
#=================================================================
with st.form(key='profile_form'):

    # アップロードテキストがあればそれを初期値にする。
    if uploaded_text:
        initial_text = uploaded_text
    else:
        # セッションステートから 'text0_value' を取得し、それがなければ空文字
        initial_text = st.session_state.get("text0_value", "")

    # メインのテキストエリア
    text0 = st.text_area(
        "エスペラントの文章を入力してください",
        height=150,
        value=initial_text  # セッションステートから読み込んだ初期値を使う
    )

    # %...% と @...@ の使い方を説明した短文を出力
    st.markdown("""「%」で前後を囲む(「%<50文字以内の文字列>%」形式)と、
    「%」で囲まれた部分は文字列(漢字)置換せず、元のまま保持することができます。""")

    st.markdown("""また、「@」で前後を囲む(「@<18文字以内の文字列>@」形式)と、
    「@」で囲まれた部分を局所的に文字列(漢字)置換します。""")

    # 出力文字形式の選択 (エスペラント特有文字の表記形式)
    letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^形式'))

    # 送信ボタンとキャンセルボタンを並べる
    submit_btn = st.form_submit_button('送信')
    cancel_btn = st.form_submit_button("キャンセル")

    # キャンセルが押された時の処理
    if cancel_btn:
        st.warning("キャンセルされました。")
        st.stop()  # ここで処理中断

    # 送信ボタンが押されたら
    if submit_btn:
        # 入力テキストをセッションステートに保存しておく
        st.session_state["text0_value"] = text0

        #=================================================================
        # ここから実際にテキストを置換して処理 (並列 or 単一プロセス)
        #=================================================================
        if use_parallel:
            processed_text = parallel_process(
                text=text0,
                num_processes=num_processes,
                placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
                replacements_list_for_localized_string=replacements_list_for_localized_string,
                placeholders_for_localized_replacement=placeholders_for_localized_replacement,
                replacements_final_list=replacements_final_list,
                replacements_list_for_2char=replacements_list_for_2char,
                format_type=format_type
            )
        else:
            processed_text = orchestrate_comprehensive_esperanto_text_replacement(
                text=text0,
                placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
                replacements_list_for_localized_string=replacements_list_for_localized_string,
                placeholders_for_localized_replacement=placeholders_for_localized_replacement,
                replacements_final_list=replacements_final_list,
                replacements_list_for_2char=replacements_list_for_2char,
                format_type=format_type
            )

        #=================================================================
        # letter_typeの指定に応じて、最終的なエスペラント文字の表記を変換する
        #  - 上付き文字 (ĉ → c + ˆ)
        #  - x 形式 (ĉ → cx)
        #  - ^ 形式 (ĉ → c^)
        #=================================================================
        if letter_type == '上付き文字':
            processed_text = replace_esperanto_chars(processed_text, x_to_circumflex)
            processed_text = replace_esperanto_chars(processed_text, hat_to_circumflex)
        elif letter_type == '^形式':
            processed_text = replace_esperanto_chars(processed_text, x_to_hat)
            processed_text = replace_esperanto_chars(processed_text, circumflex_to_hat)

        # HTML形式の場合、ヘッダーとフッターをつける (ルビ表示対応など)
        processed_text = apply_ruby_html_header_and_footer(processed_text, format_type)

#=================================================================
# =========================================
# フォーム外の処理: 結果表示・ダウンロード
# =========================================
#=================================================================
if processed_text:
    # -- ここから追加: 巨大テキスト対策ロジック（行数ベースで一部省略表示）
    MAX_PREVIEW_LINES = 250  # 250行まで表示
    lines = processed_text.splitlines()  # 改行区切りでリスト化

    if len(lines) > MAX_PREVIEW_LINES:
        # 先頭247行 + "..." + 末尾3行のプレビュー
        first_part = lines[:247]
        last_part = lines[-3:]
        preview_text = "\n".join(first_part) + "\n...\n" + "\n".join(last_part)
        st.warning(
            f"テキストが長いため（総行数 {len(lines)} 行）、"
            "全文プレビューを一部省略しています。末尾3行も表示します。"
        )
    else:
        preview_text = processed_text

    #=================================================================
    # 置換結果の表示。HTML形式の場合はプレビュータブとソースコードタブに分けて表示
    #=================================================================
    if "HTML" in format_type:
        tab1, tab2 = st.tabs(["HTMLプレビュー", "置換結果（HTML ソースコード）"])
        with tab1:
            components.html(preview_text, height=500, scrolling=True)
        with tab2:
            st.text_area("", preview_text, height=300)
    else:
        # HTML以外 (括弧形式 など) の場合はテキストタブに表示
        tab3_list = st.tabs(["置換結果テキスト"])
        with tab3_list[0]:
            st.text_area("", preview_text, height=300)

    # ダウンロードボタン
    download_data = processed_text.encode('utf-8')
    st.download_button(
        label="置換結果のダウンロード",
        data=download_data,
        file_name="置換結果.html",
        mime="text/html"
    )

st.write("---")

#=================================================================
# ページ下部に、アプリのGitHubリポジトリのリンクを表示
#=================================================================
st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")

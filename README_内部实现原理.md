# Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-Beta

以下の説明書は、本アプリのソースコード(main.py / エスペラント文(漢字)置換用のJSONファイル生成ページ.py / esp_text_replacement_module.py / esp_replacement_json_make_module.py)を「**どのように作動し、どんなデータの流れになっているのか**」を中心に、かなり踏み込んだ観点でまとめたものです。  
「GUI的な操作方法はある程度わかる」という前提で、内部で行われるテキスト置換フローや、JSON生成ロジック、モジュール同士の呼び出し順序などを解説していきます。  

---

# 目次

1. **全体アーキテクチャ概要**  
   1.1 アプリにおける「メインページ」(main.py) と「補助ページ」(エスペラント文(漢字)置換用のJSONファイル生成ページ.py)  
   1.2 文字列(漢字)置換モジュール (esp_text_replacement_module.py)  
   1.3 JSONファイル生成モジュール (esp_replacement_json_make_module.py)  

2. **メインページ: main.py の仕組み**  
   2.1 JSONファイル読み込みロジック  
   2.2 placeholders (占位符) の読み込み  
   2.3 並列処理の設定と注意点 (multiprocessing / spawn start method)  
   2.4 入力テキストの取得 (手動入力 or ファイルアップロード)  
   2.5 文字列(漢字)置換の実行フロー  
   2.6 出力形式(HTML/括弧形式/単純置換等)の反映  
   2.7 ダウンロードおよび最終表示  

3. **補助ページ: エスペラント文(漢字)置換用のJSONファイル生成ページ.py の仕組み** (JSONファイルを自分で作成したい場合)  
   3.1 CSVファイルやユーザー定義JSONファイルの取り扱い  
   3.2 置換用JSONファイル「3種類のリスト」(全域用 / 局所用 / 二文字語根用) を生成するまでの流れ  
   3.3 動詞・名詞語尾の追加など細かい語尾展開ロジック  
   3.4 大量データをどうやって合成し、優先順位(文字数×10000)を付けているか  

4. **esp_text_replacement_module.py (文字列置換モジュール) の詳細**  
   4.1 エスペラント文字表記 (ĉ → cx 等) 関連の変換関数たち  
   4.2 大域置換 / 局所置換 / skip置換(“%...%”) / placeholders の仕組み  
   4.3 orchestrate_comprehensive_esperanto_text_replacement() で行われる処理手順  
   4.4 multiprocessing の parallel_process()  

5. **esp_replacement_json_make_module.py (JSON生成のためのモジュール) の詳細**  
   5.1 CSVデータの読み込みと safe_replace() の組み合わせ  
   5.2 output_format() によるルビ付与・漢字置換のバリエーション  
   5.3 parallel_build_pre_replacements_dict() の並列化 (JSON作成時の最適化)  
   5.4 remove_redundant_ruby_if_identical() (重複ルビ除去のトリック)  

6. **補足ポイント**  
   6.1 文字数を元にした「置換優先度」の設計意図  
   6.2 Streamlit特有の注意点 (セッションステート, レイアウト, @st.cache_data, etc.)  
   6.3 大規模辞書(50MB級のJSON)を扱うときのパフォーマンス戦略  

---


## 1. 全体アーキテクチャ概要

### 1.1 アプリにおける「メインページ」(main.py) と「補助ページ」(エスペラント文(漢字)置換用のJSONファイル生成ページ.py)

- **メインページ (main.py)**  
  アプリを起動したときに表示されるメイン画面です。  
  置換に使う「JSONファイル」をロードし、ユーザーが入力したエスペラント文(手動orファイル経由)に対して「文字列(漢字)置換」を実行し、最終的なテキストをダウンロードできるようにする機能を担います。

- **補助ページ (エスペラント文(漢字)置換用のJSONファイル生成ページ.py)**  
  Streamlit には `pages/`フォルダに配置したスクリプトを「サブページ」として扱える仕組みがあります。  
  このサブページでは、「エスペラント→漢字/訳語」の対応関係を納めた CSV や、「ユーザー定義の語根分解ルール/置換後文字列」を納めた JSONファイルを使い、最終的に**巨大な置換用JSON(合并3个JSON文件)** を作るためのツールを提供しています。  
  すなわち「(エスペラント文(漢字)置換用のJSONファイル生成ページ.py)で自前の置換JSONファイルを作り、それを (main.py) に読み込ませて文章変換する」という流れを想定しています。

### 1.2 文字列(漢字)置換モジュール (esp_text_replacement_module.py)

- エスペラント特有文字 (ĉ, ĝ など) の表記ゆれを一元化する関数や、  
  `%...%` や `@...@` で囲まれたテキストを局所的にスキップ/局所置換する仕組みなど、  
  **「入力テキストをどう最終的に置換していくか」** の一連の関数が集められています。  
- Streamlit 内部で、メインの変換処理(オールインワン)を担う `orchestrate_comprehensive_esperanto_text_replacement()` や、行単位で分割して並列処理する `parallel_process()` なども本モジュールに収録されています。

### 1.3 JSONファイル生成モジュール (esp_replacement_json_make_module.py)

- 補助ページ(エスペラント文(漢字)置換用のJSONファイル生成ページ.py) での**「置換用JSONを組み立てる」**処理を支えるモジュールです。  
- CSVファイルを読み取って語根や訳語をまとめたり、動詞や名詞の語尾を付与した派生形を多数生成し、それらを**最終的に3種類**のリスト  
  1. **全域置換用のリスト (replacements_final_list)**  
  2. **二文字語根(2char root)の追加置換リスト (replacements_list_for_2char)**  
  3. **局所的置換用リスト (replacements_list_for_localized_string)**  
  にまとめ上げるまでのロジックが、関数群として実装されています。

---


## 2. メインページ: main.py の仕組み

ここでは**ユーザーが実際に置換処理を行う**ときの一連の手順を説明します。

### 2.1 JSONファイル読み込みロジック

```python
selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)
```
- **JSONファイルの扱い**  
  - 「デフォルトを使用する」を選んだ場合 → `load_replacements_lists()` 関数(後述)により、アプリ内蔵のデフォルトJSONが読み込まれる。  
  - 「アップロードする」を選んだ場合 → `st.file_uploader` からユーザーがアップロードした JSON を `json.load()` して読み込む。

```python
@st.cache_data
def load_replacements_lists(json_path: str) -> Tuple[List, List, List]:
    # JSONファイルをロードし、"全域替换用"、"局部文字替换用"、"二文字词根替换用" の3つのリストを返す
```
- Streamlit の `@st.cache_data` デコレータにより、読み込んだ JSON はキャッシュされ、**繰り返し再読込による遅延を防ぐ**ようになっています。  
- JSON内には**3つのリスト**が格納されており、`("全域替换用のリスト", "局部文字替换用のリスト", "二文字词根替换用のリスト")`を分割して取り出しているのがポイントです。

### 2.2 placeholders (占位符) の読み込み

```python
placeholders_for_skipping_replacements = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)
placeholders_for_localized_replacement = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)
```
- 「%...%」で囲った箇所をスキップするときや、「@...@」で囲った箇所を局所的に置換するときに、**置換の衝突を防ぐため**のユニークな文字列(placeholder)をファイルから読み込みます。  
- たとえば `%abc%` があったとき、まず `%abc% → (プレースホルダX)` へ仮置換し、そのあとはこの箇所が大域置換されないようブロックする、という使い方をします。

### 2.3 並列処理の設定と注意点 (multiprocessing / spawn start method)

```python
try:
    multiprocessing.set_start_method("spawn")
except RuntimeError:
    pass
```
- **Windows等の環境でmultiprocessingを使う際、エラーが出るのを防ぐため**に、`spawn` モードを明示設定しています。  
- `try-except` で囲んでいるのは、すでに別の箇所で start method が設定済みの場合を想定しているからです。  

```python
use_parallel = st.checkbox("並列処理を使う", value=False)
num_processes = st.number_input("同時プロセス数", min_value=2, max_value=4, value=4, step=1)
```
- ユーザーが**並列処理を使うかどうか**を選べる仕組みになっています。  
  - Python標準の multiprocessing.Pool を使い、**行単位**で文字列変換処理を分散実行させるのが目的です。  
  - ただし、巨大テキスト(数万行以上) でなければ並列化のオーバーヘッドが大きくなる場合もあるため、チェックボックスで選べる形になっています。

### 2.4 入力テキストの取得 (手動入力 or ファイルアップロード)

```python
source_option = st.radio("入力テキストをどうしますか？", ("手動入力", "ファイルアップロード"))
```
- どちらでも最終的には `text_area` に文字列を読み込みます。
- 手動入力の場合 → そのままユーザーがテキストを貼り付け  
- ファイルアップロードの場合 → `st.file_uploader` で読み込み、`.read().decode("utf-8")` したテキストを `text_area` の初期値として表示

### 2.5 文字列(漢字)置換の実行フロー

#### (1) 「送信」ボタンが押されたとき

```python
if submit_btn:
    # (a) テキストをセッションステートに保存
    st.session_state["text0_value"] = text0
    # (b) 並列処理 or 単一プロセスを選択
    if use_parallel:
        processed_text = parallel_process(...)
    else:
        processed_text = orchestrate_comprehensive_esperanto_text_replacement(...)
```
- ボタンが押されたら、**メインの置換処理**を呼び出します。  
  - `parallel_process()` は**行単位で分割し、プロセスプールで部分的に `orchestrate_comprehensive_esperanto_text_replacement()` を呼び出す**ヘルパー関数です。  
  - `orchestrate_comprehensive_esperanto_text_replacement()` は**すべて単一スレッドで実行**します。

#### (2) `orchestrate_comprehensive_esperanto_text_replacement()` の中で行われること

後述「4.3 orchestrate_comprehensive_esperanto_text_replacement() で行われる処理手順」をご参照ください。  
要点だけ箇条書きすると:

1. まずエスペラント文字表記(ĉ 等)を**字上符形式**(circumflex)に正規化  
2. `%...%` で囲まれた箇所をプレースホルダに置換し、**スキップ扱い**(後段で置換しないように)  
3. `@...@` で囲まれた箇所は**局所的な置換**(別リストを適用)  
4. その後、大域置換リストを適用 → `(old, new, placeholder)` の仕組みで**安全に**置換  
5. 2文字語根の置換を2回行う (ちょっと特殊なアプローチ)  
6. プレースホルダ(%)や(@)の部分を**復元**  
7. (HTML形式の場合) 改行を `<br>` に変換し、連続スペースを `&nbsp;` にする  

### 2.6 出力形式(HTML/括弧形式/単純置換等)の反映

```python
format_type = st.selectbox(
    "出力形式を選択:",
    [
        "HTML格式_Ruby文字_大小调整",
        "HTML格式_Ruby文字_大小调整_汉字替换",
        "HTML格式",
        "HTML格式_汉字替换",
        "括弧(号)格式",
        "括弧(号)格式_汉字替换",
        "替换后文字列のみ(仅)保留(简单替换)"
    ]
)
```
- この `format_type` は `orchestrate_comprehensive_esperanto_text_replacement()` 内でも参照され、**ルビタグをどう組み立てるか**、または**括弧形式で `(元単語)` を追記するか**といった出力表現が変わります。

### 2.7 ダウンロードおよび最終表示

- 出力結果 `processed_text` が得られた後、以下のような表示を行います:  
  1. **プレビュー用のテキストエリア**  
     - 大量テキストの場合は先頭数百行 + 末尾3行のみを表示し、中間を省略するようになっている。
  2. **HTML形式の場合**は2つのタブを用意  
     - タブ1: `components.html(...)` で**実際のHTMLレンダリング**をスクロール表示  
     - タブ2: `st.text_area(...)` でHTMLソースをそのまま表示  
  3. 「置換結果のダウンロード」ボタン  
     - ダウンロードする際の `mime="text/html"` は、HTMLフォーマットでも単純テキストとしてでも受け取れるようにする意図。

---


## 3. 補助ページ: エスペラント文(漢字)置換用のJSONファイル生成ページ.py の仕組み (置換用JSONファイルを自分で作りたい場合)

### 3.1 CSVファイルやユーザー定義JSONファイルの取り扱い

補助ページの目的は、**巨大な 置換用JSONファイル(合并3个JSON文件) を生成し、ダウンロードする**ことです。  

1. **CSVファイルの読み込み**  
   例えば「エスペラント語根と日本語訳の対応関係」を記したCSVなどをアップロード/デフォルト読み込みする。  
   - `pd.read_csv(...)` で2列 (語根 / 対応ルビ) を取得し、DataFrameとして保持。  

2. **ユーザー定義JSON(語根分解法/置換後文字列)の読み込み**  
   - *サンプル: `世界语单词词根分解方法の使用者自定义设置.json`*, *`替换后文字列(汉字)の使用者自定义设置.json`*  
   - これらは「特定の語根はどう分解し、どういう接尾辞を追加するか」「カスタムの(エスペラント→漢字)を定義するか」などの詳細ルールを記述するもの。  

### 3.2 置換用JSONファイル「3種類のリスト」(全域用 / 局所用 / 二文字語根用) を生成するまでの流れ

補助ページ(エスペラント文(漢字)置換用のJSONファイル生成ページ.py) の**大まかな流れ**は下記のようになります:

1. **(大規模データ読み込み)**  
   - `PEJVO(世界语全部单词列表)...json` や `世界语全部词根_约11137个_202501.txt` などの内部ファイルを開き、すべてのエスペラント語根を辞書型に格納する。  

2. **(CSVを反映)**  
   - CSV (語根→日本語/漢字) を読み込み、既存の語根辞書を**上書き or 補完**する形で置換後文字列を埋め込む。  
   - `output_format(エスペラント語根, 対応訳語, format_type, char_widths_dict)` を呼び出し、HTMLルビ形式や括弧形式など**指定フォーマット**の文字列を生成。  

3. **(単語の文字数に応じた優先順位付け)**  
   - たとえば**(文字数 × 10000)** のように、大きい数字を付与。これが**置換の優先順位**になります(文字数の多い単語から置換するように)。  

4. **(語尾・接尾辞の展開)**  
   - 動詞活用(as, is, os, us, ...)、名詞語尾(o, on, oj, ...)、形容詞語尾(a, an, aj, ...)、さらには **接頭辞**や**2文字語根**特有の展開などを大量に組み合わせて新たな候補を作り出す。  
   - 「custom_stemming_setting_list」(= ユーザー定義JSON) で定義された語根もここで**特別扱い**して追加・削除を行う。  
   - 結果として、**「〜さん」「〜たち」「〜される」「〜している」** 等のバリエーションが大量に生成されるわけです。

5. **(最終リスト3種を組み立て、JSONにまとめる)**  
   - 「全域置換用のリスト」(最も重要)  
   - 「局所置換用のリスト」( `@...@` 用 )  
   - 「二文字語根のリスト」( `al, am, av, bo...` などの特殊処理用 )  
   - これらを1つの辞書にまとめて `json.dumps(...)` し、**ダウンロードボタン**を提供する。

### 3.3 動詞・名詞語尾の追加など細かい語尾展開ロジック

エスペラント文(漢字)置換用のJSONファイル生成ページ.py の中盤以降は、非常に長い if文や for文で:

- 「**名詞**かつ文字数が6以下の場合、さらに派生形 `〜o, 〜on, 〜oj` なども追加で生成し、優先順位を `(文字数 + len('on'))×10000 - 3000` にする」  
- 「**動詞**の場合は、活用語尾(as, is, os, us... あるいは受動形 at, it, ot...)を付けた派生単語も作る」  
- 「an, on のような2文字語根に対して**o(名詞語尾)** を付ける」  
- さらにユーザーが「この語根は -1 (除外)」 と指定した場合は**辞書から消去**する  

…という処理を延々と行っています。  
これにより、非常に細かい語尾や派生形を**一括生成**できる仕組みになっています。

### 3.4 大量データをどうやって合成し、優先順位(文字数×10000)を付けているか

- **置換精度向上のため**に、「文字数の多い(複合語)」を先にマッチさせる必要があります。  
  例えば「transliterator」を「trans + liter + ator」にマッチするより先に、**「transliterator」**という長い単語として置換したい場合があります。  
- そのため、最終的には `(単語の長さ) × 10000` のように比較的大きな数値を計算し、**descending(降順)** でソートしてから**「old → placeholder → new」**としてまとめられています。


---


## 4. esp_text_replacement_module.py (文字列置換モジュール) の詳細

ここには**本番の置換**で呼ばれる重要な関数が詰め込まれています。

### 4.1 エスペラント文字表記 (ĉ → cx 等) 関連の変換関数たち

```python
x_to_circumflex = {
    'cx': 'ĉ', 'gx': 'ĝ', ...
}

def convert_to_circumflex(text: str) -> str:
    text = replace_esperanto_chars(text, hat_to_circumflex)
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text
```
- `x`形式 (cx) や `^`形式 (c^) で入力されたエスペラント文字を**最終的に ĉ, ĝ 等の字上符**に変換するための辞書が定義されています。  
- `replace_esperanto_chars()` は `str.replace()` を連続的に行うシンプルな実装です。  
- main.py 側では「最終出力」において `letter_type` を選べるようになっています(「x形式で出力」「^形式で出力」「字上符で出力」)。  
  - したがって最初にすべてを ĉ などに正規化しておき、最後にユーザーが指定した表記法に合わせて再変換する形です。

### 4.2 大域置換 / 局所置換 / skip置換(“%...%”) / placeholders の仕組み

- `%...%` に囲まれた文字列は**大域置換の影響を受けない**ように一時的にプレースホルダに置換します。 (例: `%secret% → [PLACEHOLDER_abc]`)  
- `@...@` に囲まれた文字列は**「局所置換リスト(replacements_list_for_localized_string)」だけ**を適用します。大域置換はしません。  
- これらが最終的に復元されるので、**「大域置換」 → 「局所置換部は置換対象外 or 別処理」**が実現できます。  

### 4.3 orchestrate_comprehensive_esperanto_text_replacement() で行われる処理手順

```python
def orchestrate_comprehensive_esperanto_text_replacement(
    text,
    placeholders_for_skipping_replacements,
    replacements_list_for_localized_string,
    placeholders_for_localized_replacement,
    replacements_final_list,
    replacements_list_for_2char,
    format_type
) -> str:
    # (1) 半角スペース正規化 → (2) エスペラント文字(ĉ等)に統一
    # (3) %...% スキップ部をプレースホルダに差し替え
    # (4) @...@ 局所置換を適用
    # (5) 大域置換リストを適用 (old→placeholder→new)
    # (6) 二文字語根を2回追加で置換
    # (7) placeholderを最終文字列に戻す
    # (8) HTML形式の場合、改行→<br>、スペース→&nbsp;変換
```
順番をおさらいすると:

1. **`unify_halfwidth_spaces(text)`**: 半角スペースっぽい文字(U+00A0など)をASCII半角スペースに統一  
2. **`convert_to_circumflex(text)`**: `cx, c^` 等を `ĉ` に変換 (先述)  
3. **%スキップ**  
   - `create_replacements_list_for_intact_parts(text, placeholders_for_skipping_replacements)` → `%abc%` の個所を**特殊プレースホルダ**に変換  
   - 変換後、一時的に `%abc% → [PLACEHOLDER]` となる  
4. **@局所置換**  
   - `create_replacements_list_for_localized_replacement()` で抽出した文字列だけ**「局所置換リスト」**を適用  
   - その結果 `@abc@ → (一時プレースホルダX)` となり、内部では**CSV由来の小さな置換**だけ実行  
5. **大域置換**(replacements_final_list)  
   - `(old, new, placeholder)` の形式を使い、「old → placeholder → new」という2段階置換を実行  
   - いきなり `old → new` とやると、置換対象文字列が重複してまた置換される等の**衝突**が起きる恐れがあるため、  
     **一旦 placeholder を挟む** ことで安全性を高めています。  
6. **2文字語根の置換(2回)**  
   - `replacements_list_for_2char` は接頭辞/接尾辞レベルの単語に使う特殊置換。  
   - なぜ2回やるのか → 2文字語根の場合に、1回の置換後にさらに別の2文字とマッチさせたいケースがあるから(詳細はコード参照)。  
7. **復元**  
   - `%...%` / `@...@` でプレースホルダ化していた部分を元に戻す  
8. **HTML整形**  
   - もし `format_type` が `HTML*` 系なら、改行→`<br>`、スペース→`&nbsp;` に変換  
   - `apply_ruby_html_header_and_footer()` で `<style>` や `<body>` タグを付け足す  

### 4.4 multiprocessing の parallel_process()

```python
def parallel_process(
    text: str,
    num_processes: int,
    placeholders_for_skipping_replacements,
    replacements_list_for_localized_string,
    ...
    format_type: str
) -> str:
    # textを行単位に分割し、分割した部分を
    # Pool.starmap(process_segment, [...]) で並列処理
    # 最後に''.joinして返す
```

- ユーザーが選んだ「同時プロセス数」だけプロセスを立ち上げ、  
  テキストを**行単位**で分割して `process_segment()` を実行させる仕組みです。  
- `process_segment()` は単に `orchestrate_comprehensive_esperanto_text_replacement()` を呼び出すだけなので、**並列実行の粒度は「行」**です。  
  - 行数が非常に多いテキスト (大量文章) であれば高い効果が期待できる反面、分割単位が不均一だと速度が出にくい場合がある点に注意が必要です。

---


## 5. esp_replacement_json_make_module.py (JSON生成モジュール) の詳細

補助ページ (エスペラント文(漢字)置換用のJSONファイル生成ページ.py) が主にこのモジュールの関数を呼び出して**最終的なJSONを組み立て**ています。

### 5.1 CSVデータの読み込みと safe_replace() の組み合わせ

- CSVから読み込んだ (エスペラント語根, 訳語ルビ) のペアを大量に保持したのち、  
  それらを `safe_replace()` などを使い、**一括で「文字列(漢字)を置換しやすい形式」に変換**していきます。  
- 同名関数 `safe_replace()` が main.py 側にもあり、エスペラント文(漢字)置換用のJSONファイル生成ページ.py 側にもあるのは**重複定義**ですが、呼び出し元が異なるため両方に同居しています。

### 5.2 output_format() によるルビ付与・漢字置換のバリエーション

```python
def output_format(main_text, ruby_content, format_type, char_widths_dict):
    # format_type に応じて、HTMLルビ、括弧形式、単純置換などを生成する
```
- たとえば `format_type == 'HTML格式_Ruby文字_大小调整'` のときは、「文字幅」に応じて `<rt class="L_L">` などを付け分ける実装がなされています。  
  - `measure_text_width_Arial16()` や `insert_br_at_half_width()` などを使い、**ルビ文字列が親文字列より長い場合に改行**する等の処理が行われる。  
- `括弧(号)格式` の場合は単に `main_text(ruby_content)` のように括弧で括るだけ、  
- `替换后文字列のみ(仅)保留(简单替换)` の場合は `ruby_content` だけ出す、など**まとめて出力形態を切り替える**仕組みです。

### 5.3 parallel_build_pre_replacements_dict() の並列化 (JSON作成時の最適化)

```python
def parallel_build_pre_replacements_dict(
    E_stem_with_Part_Of_Speech_list,
    replacements,
    num_processes
) -> Dict[str, List[str]]:
    # E_stem_with_Part_Of_Speech_listを分割し、
    # process_chunk_for_pre_replacements() を並列に実行してマージ
```
- (エスペラント文(漢字)置換用のJSONファイル生成ページ.py) で使われる関数。**エスペラントの語根 + 品詞情報**を大量に抱えたリストを分割し、各パートで `safe_replace()` して部分的な結果辞書を返し、それを最終的にマージする。  
- **数万〜数十万規模**のデータを扱うときに速度向上が見込めます。

### 5.4 remove_redundant_ruby_if_identical() (重複ルビ除去のトリック)

```python
IDENTICAL_RUBY_PATTERN = re.compile(r'<ruby>([^<]+)<rt class="XXL_L">([^<]+)</rt></ruby>')
def remove_redundant_ruby_if_identical(text: str) -> str:
    # <ruby>xxx<rt class="XXL_L">xxx</rt></ruby> のような
    # 親文字列とルビが完全に同じ場合は <ruby>...</ruby> を除去して xxx にする
```
- CSVなどで「エスペラント単語」と「同じ文字列(漢字変換前後で同じ)」がマッピングされた場合などにルビを重複させても意味が無いので、  
  このように**正規表現で「<ruby>xxx<rt>xxx</rt></ruby> を置き換える」**実装をしているわけです。


---


## 6. 補足ポイント

### 6.1 文字数を元にした「置換優先度」の設計意図

- 「(old単語の文字数) × 10000」 というのが、エスペラント文(漢字)置換用のJSONファイル生成ページ.py コード内の**肝**になっています。  
- 文字数が長い単語ほど優先度が高い → **前方一致でマッチしたときに、短い語根に先に置換されてしまう」誤置換を防ぐ**ための仕組みです。  
- 例: "kanto" という語根より "kanton" "kantalupo" など6文字・7文字の複合語を先に置換すべき場合があります。

### 6.2 Streamlit特有の注意点 (セッションステート, レイアウト, @st.cache_data, etc.)

- **`st.session_state`**  
  - メインページでユーザーが入力したテキストをフォーム提出後も保持するために使っています。  
- **`@st.cache_data`**  
  - JSONファイルの読み込みをキャッシュしておき、**何度もロードする際にリソースを節約**します。  
- **ページレイアウト**  
  - `st.set_page_config(layout="wide")` や `components.html()` などで横幅を広く使い、HTMLプレビューを埋め込めるようにしている。  

### 6.3 大規模辞書(50MB級のJSON)を扱うときのパフォーマンス戦略

- **@st.cache_data** の活用により、再読み込みを抑制する。  
- **multiprocessing** での行単位並列化を有効活用する(特に main.py)。  
- **エスペラント文(漢字)置換用のJSONファイル生成ページ.py** 側の JSON 生成も、parallel_build_pre_replacements_dict() で**部分的に並列化**。  
- ただし Windows + Python + Streamlit の環境だとプロセスの立ち上げにオーバーヘッドがあるので、**テキスト行数がそこそこ大量**の場合にのみ効果がある。


---

# まとめ

本アプリは、**「エスペラント文を(漢字)置換する」**というニッチな要件に合わせて、非常に細かい語根展開・品詞展開が実装されています。  

- `main.py` ではユーザーが最終的に「置換用JSON(3つのリスト)」を読み込み、テキストを入力して**一括変換**するのがメイン機能。  
- `エスペラント文(漢字)置換用のJSONファイル生成ページ.py` では「それに使う巨大な JSON(合并済み) をどうやって作るか？」を**GUI上で実行可能**な形にしています。  
- `esp_text_replacement_module.py` と `esp_replacement_json_make_module.py` は、それぞれ  
  - **文字列置換の本体**(大域置換/局所置換/並列化/ルビ付加/スペース置換)  
  - **置換用データ(語根/訳語/語尾展開等)を扱う際のツール群**  
  をまとめたモジュールという位置づけです。

本番環境(クラウド or ローカル)で実際に動かす際は、**テキストが大きい場合に並列処理をONにする**などパフォーマンス面の工夫をすると効果的です。またユーザー定義JSONによって**細かい派生形をどう生成するか**も柔軟に変更できるため、大規模・緻密な翻訳ルールを扱う場合に適した設計になっています。  

以上が、本アプリの仕組みを理解するためのポイントです。GUI操作はある程度わかっているとのことでしたので、**内部実装(どうやって置換フローを進めているか、どこでデータが合成されるか)** に注目して解説しました。実際の運用・改修の際には、ぜひ各モジュールの該当関数をカスタマイズしながら進めてみてください。  

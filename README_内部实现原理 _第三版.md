# Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool

以下の説明書は、本アプリのソースコード(main.py / エスペラント文(漢字)置換用のJSONファイル生成ページ.py / esp_text_replacement_module.py / esp_replacement_json_make_module.py)を「**どのように作動し、どんなデータの流れになっているのか**」を中心に、かなり踏み込んだ観点でまとめたものです。  
「GUI的な操作方法はある程度わかる」という前提で、内部で行われるテキスト置換フローや、JSON生成ロジック、モジュール同士の呼び出し順序などを解説していきます。  

---

# 目次

1. **アプリ全体像：コードの構成と役割**
2. **メインページ（`main.py`）の仕組み**
   - 2.1. JSONファイル読み込み（置換ルール）
   - 2.2. 占位符（placeholders）のロード
   - 2.3. 並列処理とマルチプロセス
   - 2.4. テキスト入力とフォーム送信処理
   - 2.5. 実際の文字列(漢字)置換のフロー
   - 2.6. 出力形式のエスペラント文字表記変換（上付き／x形式／^形式）
   - 2.7. 結果の表示とダウンロード
3. **サブページ（`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`）の仕組み**
   - 3.1. CSV の取り込み
   - 3.2. JSON（語根分解法・置換後文字列設定）の取り込み
   - 3.3. 大量の語根データを使った置換リスト生成
   - 3.4. 出力形式（HTML/括弧形式/単純置換等）への対応
   - 3.5. 結合結果を JSON 化 → ダウンロード
4. **`esp_text_replacement_module.py` の詳細**
   - 4.1. エスペラント文字変換（cx→ĉ 等）
   - 4.2. `%...%` と `@...@` の扱い（skip/局所置換）
   - 4.3. 大域置換 → 最終復元フロー
   - 4.4. 並列処理 `parallel_process`
   - 4.5. HTMLヘッダー付与（ルビ表示用CSS）
5. **`esp_replacement_json_make_module.py` の詳細**
   - 5.1. CSV 読み込み＋語根展開→優先度付け
   - 5.2. `output_format(...)` によるルビ付与・括弧形式
   - 5.3. 文字幅測定（`measure_text_width_Arial16`) と `<br>` 挿入
   - 5.4. `parallel_build_pre_replacements_dict` を使った大規模並列化
6. **設計上のポイント・注意点**
   - 6.1. 置換衝突回避のための “placeholder法”
   - 6.2. 動詞活用語尾や形容詞語尾を自動的に足すロジック
   - 6.3. 同一ルビの除去 `remove_redundant_ruby_if_identical`
   - 6.4. JSON の 3 リスト構成（全域 / 2文字語根 / 局所）
   - 6.5. Streamlit 固有の制約と @st.cache_data, multiprocessing
7. **まとめ**

---

## 1. アプリ全体像：コードの構成と役割

アプリは以下の4つの Python ファイルで構成されています：

1. **`main.py`**  
   - **メインページ**（Streamlitアプリの起点）  
   - GUIからのテキスト入力・変換を行う中枢。  
   - JSONファイル（置換ルール）を読み込み、`esp_text_replacement_module.py` の関数を呼んで実際の置換を実行します。

2. **`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`**  
   - **サブページ**（同じStreamlitアプリ内）  
   - CSV、ユーザー定義JSONを読み込み、大量の語根データを合成して**置換用JSON**を生成 → ダウンロードするためのツール。  
   - 後述の `esp_replacement_json_make_module.py` を呼び出してロジックを実装。

3. **`esp_text_replacement_module.py`**  
   - **エスペラント文の置換処理モジュール**  
   - `%...%`（skip）や `@...@`（局所）を活用した処理、エスペラント文字の表記揺れ統一（cx→ĉ 等）を含む。  
   - 「メインページでユーザーが入力したテキスト」をどうやって変換するかの本体。

4. **`esp_replacement_json_make_module.py`**  
   - **置換用JSONファイルを作る際に使う機能**をまとめたモジュール  
   - CSV合体、語根分解、Rubyタグ生成、文字幅計測などを行い、最終的に大規模JSONを作り上げる。

Streamlitでは、起動時に `main.py` が最初のページとして読み込まれ、`pages/` フォルダの `.py` ファイルがサブページとしてメニューに並びます。ユーザーは GUI 上で必要に応じてメインページとサブページを行き来しつつ使う想定です。

---

## 2. メインページ（`main.py`）の仕組み

### 2.1. JSONファイル読み込み（置換ルール）

```python
selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)
```

- JSONには**大域置換用リスト**・**局所置換用リスト**・**二文字語根置換用リスト**の3種が含まれています。  
- `load_replacements_lists()` は `@st.cache_data` でラップされ、**キャッシュ**している点が特徴。大容量JSON（50MB級）を何度も読み込むと遅いため、キャッシュ化して高速化を図っています。

```python
def load_replacements_lists(json_path: str) -> Tuple[List, List, List]:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    ...
    return (replacements_final_list, replacements_list_for_localized_string, replacements_list_for_2char)
```
- 返ってきた 3つのリストをそれぞれグローバル変数に格納し、後段の処理で活用します。

### 2.2. 占位符（placeholders）のロード

```python
placeholders_for_skipping_replacements = import_placeholders("...文字列替换skip用.txt")
placeholders_for_localized_replacement = import_placeholders("...局部文字列替换用.txt")
```
- `%...%` で囲った文字列を置換スキップする際、`@...@` で囲った文字列を局所置換する際、**衝突を避ける**ためのユニークなプレースホルダ文字列を大量に用意しています。  
- `import_placeholders()` はテキストファイルを1行ずつ読み込むだけの単純な処理。

### 2.3. 並列処理とマルチプロセス

```python
use_parallel = st.checkbox("並列処理を使う", value=False)
num_processes = st.number_input("同時プロセス数", min_value=2, max_value=4, ...)
```
- ユーザーが並列処理を ON にすると、テキスト行単位で分割し、`multiprocessing.Pool` で並列に置換を実行します。（`parallel_process()` が本体）  
- Windows/Streamlit 環境でPicklingErrorが出ないように `spawn` モードを明示設定している点も要注意。

### 2.4. テキスト入力とフォーム送信処理

```python
with st.form(key='profile_form'):
    text0 = st.text_area("エスペラントの文章を入力してください", value=initial_text)
    ...
    submit_btn = st.form_submit_button('送信')
```
- ユーザーが入力したテキストを `st.text_area()` から受け取り、`submit_btn` クリックで処理を開始します。  
- Session State (`st.session_state`) を使ってフォーム内容を保持しているため、ページリロードでもテキストが消えない工夫がされています。

### 2.5. 実際の文字列(漢字)置換のフロー

送信ボタン押下時：

1. **並列処理を使うかどうか**で分岐  
   ```python
   if use_parallel:
       processed_text = parallel_process(...)
   else:
       processed_text = orchestrate_comprehensive_esperanto_text_replacement(...)
   ```
2. `parallel_process(...)` はテキストを行単位で分割 → `process_segment(...)` → 内部で `orchestrate_comprehensive_esperanto_text_replacement(...)` を行う。  
3. **`orchestrate_comprehensive_esperanto_text_replacement`** の処理内容は後述（esp_text_replacement_module.py）に詳しく書かれています。  
   - `%...%` → skip  
   - `@...@` → 局所置換  
   - 大域置換リスト → 2文字語根 → 復元  

### 2.6. 出力形式のエスペラント文字表記変換（上付き／x形式／^形式）

```python
if letter_type == '上付き文字':
    processed_text = replace_esperanto_chars(processed_text, x_to_circumflex)
    processed_text = replace_esperanto_chars(processed_text, hat_to_circumflex)
elif letter_type == '^形式':
    processed_text = replace_esperanto_chars(processed_text, x_to_hat)
    processed_text = replace_esperanto_chars(processed_text, circumflex_to_hat)
```

- ユーザーが「上付き文字」選択時は `cx`→`ĉ`→`c + ˆ` のように再変換を行う仕組み。  
- 最初にテキストを正規化（cx, c^ → ĉ）してから、最終出力段階で指定表記に戻している点がポイント。

### 2.7. 結果の表示とダウンロード

- 結果テキストを**最大250行まで**プレビューし、それ以上は省略表示。  
- HTML形式の場合、`components.html(...)` により実際の Ruby レンダリングを埋め込む。  
- ダウンロードボタンでは `file_name="置換結果.html"` とし、HTMLとして保存できるようにしている。

---

## 3. サブページ（`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`）の仕組み

メインページとは別に、`pages/` フォルダにあるこのファイルが呼ばれ、**大量のエスペラント語根→漢字(日本語訳)対応表を合体して置換用 JSON を作る**ことが可能になります。

### 3.1. CSV の取り込み

```python
csv_choice = st.radio("CSVファイルをどうしますか？", ("アップロードする", "デフォルトを使用する"))
...
CSV_data_imported = pd.read_csv(csv_buffer, encoding="utf-8", usecols=[0, 1])
```
- ユーザーが CSV をアップロードするか、デフォルトを使うか。  
- CSV 内には「(エスペラント語根, 翻訳文字列)」のペアが行ごとに並んでいる前提。  
- 読み込み直後に `convert_to_circumflex(...)` をかけて **エスペラント文字を正規化** している。

### 3.2. JSON（語根分解法・置換後文字列設定）の取り込み

```python
json_choice = st.radio(..., ("アップロードする", "デフォルトを使用する"))
custom_stemming_setting_list = json.load(uploaded_json)
```
- ここで「語根分解法」や「置換後文字列のカスタム」などの設定を読み込む。  
- 例：`["am", "dflt", ["verbo_s1"]]` → 語根 "am" に動詞活用を付与、など。  
- これらの JSON を後の大規模合成処理で適用します。

### 3.3. 大量の語根データを使った置換リスト生成

```python
if st.button("置換用JSONファイルを作成する"):
    # 大規模データ(PEJVO一覧) などを読み込んで...
    # CSV との突合せで temporary_replacements_list_final を作る
    # さらに parallel_build_pre_replacements_dict(...) を呼ぶ
    ...
```
1. **既存の全語根**(約11137個)を辞書 `temporary_replacements_dict` に入れる。  
2. **CSVの語根→訳語** を上書き反映し、文字数に基づく優先順位を計算。  
3. placeholder割り当て → **`temporary_replacements_list_final`** を作成。  
4. **`parallel_build_pre_replacements_dict`** により、数万行レベル（PEJVOなど）を並列処理して、最終置換後データを得る。  
5. 名詞・動詞・形容詞などに合わせて語尾（o, on, as, is, ...）を付与するロジックを行い、多数の派生を生成。  
6. これらを1つにまとめ、**(全域 / 2文字語根 / 局所)** の3リストに整形して JSON 化。

### 3.4. 出力形式（HTML/括弧形式/単純置換等）への対応

```python
format_type = ...  # "HTML格式_Ruby文字_大小调整" 等を選択
output_format(E_root, hanzi_or_meaning, format_type, char_widths_dict)
```
- `output_format(...)` の中で、HTMLルビや括弧 `( )` などの形式を組み立てます。  
- 文字数比率に応じて `<rt class="XL_L">` のようにサイズ指定を変える仕組みもここに実装されている。

### 3.5. 結合結果を JSON 化 → ダウンロード

```python
combined_data = {
  "全域替换用のリスト(列表)型配列(replacements_final_list)": replacements_final_list,
  "二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)": replacements_list_for_2char,
  "局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)": replacements_list_for_localized_string,
}
download_data = json.dumps(combined_data, ensure_ascii=False, indent=2)
st.download_button(...)
```
- この JSON ファイルをダウンロードしておけば、**メインページ**で「アップロードする」選択時に読み込んで活用できます。

---

## 4. `esp_text_replacement_module.py` の詳細

メインページの実際の置換処理は、このモジュール内の関数群を呼び出すことで行われています。

### 4.1. エスペラント文字変換（cx→ĉ 等）

```python
x_to_circumflex = {'cx': 'ĉ', 'gx': 'ĝ', ...}
def convert_to_circumflex(text: str) -> str:
    text = replace_esperanto_chars(text, hat_to_circumflex)
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text
```
- 同様に `x_to_hat`, `circumflex_to_hat` 等、さまざまな辞書が用意され、ユーザーが希望する表記形式へ変換します。

### 4.2. `%...%` と `@...@` の扱い（skip/局所置換）

- `%...%` 部分は **「create_replacements_list_for_intact_parts」** で見つけ出し、任意の placeholder に差し替えて、大域置換から守ります。  
- `@...@` 部分は **「create_replacements_list_for_localized_replacement」** で別処理をします。中の文字列だけ**局所置換リスト**で置換。  
- 最後に「プレースホルダ→元の文」に戻す段階で `%` や `@` が復元されるため、大域置換の衝突を回避できます。

### 4.3. 大域置換 → 最終復元フロー

**`orchestrate_comprehensive_esperanto_text_replacement()`** がメインで呼ばれる関数。  
大きな手順は以下の通り：

1. **空白の正規化、エスペラント文字正規化**  
2. `%...%` スキップ部 → placeholder 置換  
3. `@...@` 局所部 → 別のリストで置換 → placeholder  
4. **大域置換**  
5. **2文字語根の置換を2回実行**（prefix, suffix, standaloneを2段階で適用）  
6. placeholder から **元の文字列**に復元  
7. HTML形式なら改行→`<br>`, スペース→`&nbsp;` に整形

### 4.4. 並列処理 `parallel_process`

```python
def parallel_process(...):
    # textを行単位に分割し、process_segment() をマルチプロセスで呼ぶ
```
- `text` を正規表現 `re.findall(r'.*?\n|.+$', text)` により行ごとにスライスしてプールに渡します。  
- `process_segment()` では単に行を結合→`orchestrate_comprehensive_esperanto_text_replacement()` を呼ぶだけ。  
- 結果を結合して最終テキストにします。

### 4.5. HTMLヘッダー付与（ルビ表示用CSS）

```python
def apply_ruby_html_header_and_footer(processed_text: str, format_type: str) -> str:
    if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换'):
        # 凝ったCSSを付与
    elif format_type in ('HTML格式','HTML格式_汉字替换'):
        # 簡単な <style> だけ
    else:
        # 何もしない
```
- ルビのサイズや位置を調整するためのフレックスレイアウトCSSが書かれています。  
- `<rt class="S_S">` などサイズ階層ごとに `margin-top` を変えているのが特徴。

---

## 5. `esp_replacement_json_make_module.py` の詳細

サブページ（JSON生成）で呼ばれるモジュールです。

### 5.1. CSV 読み込み＋語根展開→優先度付け

- CSV (語根 / 漢字) を読み込み → 文字数(長さ)×10000 等で優先度を決め、**desc(降順)** に並べます。  
- 「文字数の多い単語を先に置換し、短い語根が重複置換しないようにする」ことが狙い。

### 5.2. `output_format(...)` によるルビ付与・括弧形式

```python
def output_format(main_text, ruby_content, format_type, char_widths_dict):
    if format_type == 'HTML格式_Ruby文字_大小调整':
        # 文字幅を測ってクラスを可変
    elif format_type == '括弧(号)格式':
        return f'{main_text}({ruby_content})'
    ...
```
- 例えば `HTML格式_Ruby文字_大小调整_汉字替换` を選ぶと、「メイン部分＝漢字」「Ruby部分＝エスペラント」的に書き換える実装が含まれています。  
- 行数(文字幅)に応じて `<br>` を挿入してルビが折り返しされる場合もある。

### 5.3. 文字幅測定（`measure_text_width_Arial16`) と `<br>` 挿入

- `char_widths_dict` は JSONファイル `"Unicode_BMP全范围文字幅(宽)_Arial16.json"` から読み込んだ 「文字→幅(px)」のマップ。  
- これを合計し、例えば半分に到達したら `<br>` を挿入、などのロジックを `insert_br_at_half_width` / `insert_br_at_third_width` で行っています。

### 5.4. `parallel_build_pre_replacements_dict` を使った大規模並列化

```python
def parallel_build_pre_replacements_dict(E_stem_with_Part_Of_Speech_list, replacements, num_processes=4):
    # E_stem_with_Part_Of_Speech_listを分割し、process_chunk_for_pre_replacements()を並列実行
```
- CSVに加えて**数万件の PEJVOリスト**など大規模な辞書を扱う場合、シングルスレッドでは時間がかかるため並列化。  
- chunk分割 → `process_chunk_for_pre_replacements` → partial_dict をマージ → 最終辞書（置換済み）を得る流れ。

---

## 6. 設計上のポイント・注意点

### 6.1. 置換衝突回避のための “placeholder法”

- 多段階置換（大きい単語→小さい単語）で衝突が起こると、重複置換や意図しない変換が発生しがち。  
- このアプリでは **`old → placeholder → new`** の2段階置換をとおし、「oldが途中で再度マッチする」事態を防ぎます。  
- `%...%` / `@...@` の特殊区画についても placeholder を挟むことで、大域置換の影響を受けないようにしています。

### 6.2. 動詞活用語尾や形容詞語尾を自動的に足すロジック

- サブページの処理コード中で、名詞 (o, on, oj...)、動詞 (as, is, os, us, it, at...) などの活用語尾を付与し、そのぶん文字数を増やして優先度を上げるという仕組みが入っています。  
- 例：2文字語根 `am` を「amas, amis, amos, ...」等、機械的に大量生成し、各派生形をそれぞれ文字数順に並べて一括管理。

### 6.3. 同一ルビの除去 `remove_redundant_ruby_if_identical`

- `<ruby>xxx<rt class="XXL_L">xxx</rt></ruby>` のように、親文字列とルビ文字列が同じときは無駄なので `<ruby>` タグを消す。  
- これは `IDENTICAL_RUBY_PATTERN` の正規表現で `xxx<rt>xxx</rt>` を見つけ、該当箇所だけ親文字 `xxx` に戻しています。

### 6.4. JSON の 3 リスト構成（全域 / 2文字語根 / 局所）

- **全域**：`replacements_final_list`  
  - ほぼすべての単語を網羅する通常の置換。  
- **2文字語根**：`replacements_list_for_2char`  
  - 二文字だけで成立するエスペラント語根（`al`, `am` など）や接頭辞/接尾辞を2回適用するための専用リスト。  
  - `orchestrate_comprehensive_esperanto_text_replacement()` では、これを**2連続**で適用し、複合的に置換できるようにしています。  
- **局所**：`replacements_list_for_localized_string`  
  - `@...@` 内の文字列を変換するときだけ使う（大域とは別に管理）。

### 6.5. Streamlit 固有の制約と @st.cache_data, multiprocessing

- **`@st.cache_data`**：JSONやCSVを繰り返し読み込むたびに遅くならないようにキャッシュしている。  
- **Multiprocessing**：Windows では `spawn` モードを要求されるため `try-except` で `set_start_method("spawn")` している。  
- Streamlit Cloud など一部環境では parallel 処理が制限されることもあるため、その場合 OFF にする設計になっている。

---

## 7. まとめ

- **メインページ (`main.py`)**  
  - ユーザーが入力したテキストに対し、読み込んだ JSONルール（大域/局所/2文字語根）を使って一括置換します。  
  - `%...%` スキップ、`@...@` 局所、並列処理による高速化などがポイント。  
  - 仕上げにユーザーが選んだ表記（`^`形式や上付き）への再変換や HTMLヘッダー付与を行い、画面表示＋ダウンロードします。

- **サブページ (`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`)**  
  - 大量の語根 (CSV＋PEJVO等) とユーザー定義 JSON を合体・整理して、最終的に置換用 JSON を作る。  
  - 「名詞語尾/動詞活用/接頭辞」などを自動で付加して文字数を増やし、優先度を上げる仕組みが盛り込まれています。  
  - 出力形式（HTML / 括弧 / 簡易）に合わせて `<ruby>..</ruby>` や `( )` を差し込む。

- **モジュール 2つ (`esp_text_replacement_module.py`, `esp_replacement_json_make_module.py`)**  
  - 前者は「テキスト置換の本体」: `%` `@` 処理、並列処理、HTML化など。  
  - 後者は「JSONを作る際の補助」: CSVマージ、語根展開、文字幅測定、ルビ出力など。

システム全体としては「まずサブページで置換用 JSON を作り、メインページでその JSON を使って実際に文章を置換する」という流れを想定しています。  
内部実装の肝は、**placeholder 法** と **(old→placeholder→new)** の段階的置換により衝突を防ぐ点、並列処理で大規模テキストを高速化する点、エスペラント文字の多種表記（cx形式、^形式、ĉ形式）へ柔軟に対応している点です。

以上が本アプリの仕組みを理解するための要点です。GUI操作を把握済みで「内部的にどこで何をしているのか」を知りたい方へ向け、できるだけコードと絡めて解説しました。ぜひソースコードをあわせてご確認いただき、カスタマイズや拡張の参考にしていただければ幸いです。

# Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool


以下では、アプリ全体の**内部的な仕組み**を把握したい「プログラマー」向けに、4 つの主要ファイル  
- **main.py**  
- **エスペラント文(漢字)置換用のJSONファイル生成ページ.py**  
- **esp_text_replacement_module.py**  
- **esp_replacement_json_make_module.py**  

のソースコード全体像を整理しながら、その構成・動作フロー・各主要関数の役割・モジュール間の連携などを詳しく説明します。GUI 上の使い方は既にある程度把握されている前提として、「内部ロジックをどう実現しているか」に着目して解説していきます。

---

# 目次

1. [アプリの全体構成と起動シーケンス](#アプリの全体構成と起動シーケンス)  
2. [main.py - メインアプリの仕組み](#mainpy---メインアプリの仕組み)  
   1. [起動時の初期化](#起動時の初期化)  
   2. [JSONファイル読み込み部分](#jsonファイル読み込み部分)  
   3. [占位符(placeholders) のインポート](#占位符placeholders-のインポート)  
   4. [「並列処理」スイッチの実装](#並列処理スイッチの実装)  
   5. [テキストの入力手段とフォーム](#テキストの入力手段とフォーム)  
   6. [送信ボタン押下時のメイン処理フロー](#送信ボタン押下時のメイン処理フロー)  
   7. [出力文字形式 (上付き/x形式/^形式) の変換](#出力文字形式-上付きx形式形式-の変換)  
   8. [結果表示とダウンロード機能](#結果表示とダウンロード機能)  
3. [エスペラント文(漢字)置換用のJSONファイル生成ページ.py - 仕組み](#エスペラント文漢字置換用のjsonファイル生成ページpy---仕組み)  
   1. [このページの役割](#このページの役割)  
   2. [ステップ別の処理 (CSVファイル/JSONファイル 読み込み)](#ステップ別の処理-csvファイルjsonファイル-読み込み)  
   3. [高度な設定 (並列処理)](#高度な設定-並列処理)  
   4. [最終的なJSONファイル生成フロー](#最終的なjsonファイル生成フロー)  
   5. [内部的な優先順位計算と辞書の統合](#内部的な優先順位計算と辞書の統合)  
4. [esp_text_replacement_module.py - 主要関数とロジック](#esp_text_replacement_modulepy---主要関数とロジック)  
   1. [エスペラント文字表記変換 (x形式/hat形式 ⇔ ĉ など)](#エスペラント文字表記変換-x形式hat形式--ĉ-など)  
   2. [占位符/局所置換/@...@ スキップ/%...% の仕組み](#占位符局所置換--スキップ--の仕組み)  
   3. [大域置換 (replacements_final_list) と 2文字語根置換](#大域置換-replacements_final_list-と-2文字語根置換)  
   4. [最終合成関数 orchestrate_comprehensive_esperanto_text_replacement](#最終合成関数-orchestrate_comprehensive_esperanto_text_replacement)  
   5. [並列処理 (multiprocessing) 周り (parallel_process, process_segment)](#並列処理-multiprocessing-周り-parallel_process-process_segment)  
   6. [HTML出力の仕上げ (apply_ruby_html_header_and_footer)](#html出力の仕上げ-apply_ruby_html_header_and_footer)  
5. [esp_replacement_json_make_module.py - JSON生成ロジック](#esp_replacement_json_make_modulepy---json生成ロジック)  
   1. [output_format 関数 (HTML/括弧形式など) の詳細](#output_format-関数-html括弧形式など-の詳細)  
   2. [大量のエスペラント語根を辞書化→並列で置換→優先度順にソート](#大量のエスペラント語根を辞書化並列で置換優先度順にソート)  
   3. [重複ルビ・大文字化補正などの最終加工](#重複ルビ大文字化補正などの最終加工)  
6. [モジュール間連携のまとめ](#モジュール間連携のまとめ)  
7. [補足: multiprocessing.set_start_method("spawn") の背景](#補足-multiprocessingset_start_methodspawn-の背景)  

---

## 1. アプリの全体構成と起動シーケンス

- **`main.py`**:  
  Streamlit アプリのメインページ。  
  ユーザーがアップロードしたテキストに対して **読み込んだJSON(置換ルール)** を用いて**文字列(漢字)置換**を行い、その結果を HTMLプレビューやテキストとして表示/ダウンロードする。  
  - 内部では `esp_text_replacement_module.py` の関数を使って置換。  
- **`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`**:  
  Streamlit の pages/フォルダにある追加ページ。  
  ユーザーが CSV (エスペラント語根→漢字など) ＋ 各種 JSON を読み込み、最終的に**巨大な置換ルール JSON** を自動生成するためのページ。  
  - 内部では `esp_replacement_json_make_module.py` と `esp_text_replacement_module.py` の一部関数を使用。  
- **`esp_text_replacement_module.py`**:  
  **実際の置換ロジック**(大域置換、%や@の扱い、エスペラント文字表記変換、並列処理) がまとまったモジュール。  
  - `main.py` がこのモジュールを import して使う。  
- **`esp_replacement_json_make_module.py`**:  
  **置換用 JSON生成のための下請け関数群** (並列で大量のエスペラント語根を処理したり、出力形式を HTMLルビ/括弧形式に変換するなど)。  
  - 「JSONファイル生成ページ」で主に呼び出される。  

**起動時は** `main.py` が Streamlit アプリとしてロードされ、ユーザーがサイドバーやページメニューで別ページ (`エスペラント文(漢字)置換用のJSONファイル生成ページ.py`) を開くことができます。  
いずれも**同一セッション内**で4つの Python ファイルを参照しているため、`esp_text_replacement_module.py` や `esp_replacement_json_make_module.py` は両ページで共用されます。

---

## 2. main.py - メインアプリの仕組み

### 2.1 起動時の初期化

```python
import streamlit as st
import re
import io
import json
import pandas as pd
from typing import List, Dict, Tuple, Optional
import streamlit.components.v1 as components
import multiprocessing

# ...
# multiprocessing.set_start_method("spawn") (PicklingError 回避)
```

- この冒頭部で、必要なライブラリを import すると共に、**`multiprocessing.set_start_method("spawn")`** を試みます。  
  - これは streamlit上でマルチプロセスを行う際のエラー (PicklingError) を回避するための定型措置です。

### 2.2 JSONファイル読み込み部分

```python
@st.cache_data
def load_replacements_lists(json_path: str) -> Tuple[List, List, List]:
    # JSONファイルをロードし、3つのリストを返す
    # 1) replacements_final_list
    # 2) replacements_list_for_localized_string
    # 3) replacements_list_for_2char
```

- **`@st.cache_data`** デコレータにより、ファイル読み込み結果をキャッシュ (同じファイルを再度読み込む際に高速化)。  
- JSONファイルが想定するキー:  
  - `"全域替换用のリスト(列表)型配列(replacements_final_list)"`  
  - `"局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)"`  
  - `"二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)"`  

ユーザーが**「デフォルトを使用する / アップロードする」**を選ぶと、この関数によって JSON が読み込まれ、3 つのリストに格納されます。  

### 2.3 占位符(placeholders) のインポート

```python
from esp_text_replacement_module import (
    x_to_circumflex,
    x_to_hat,
    ...
    import_placeholders,
    orchestrate_comprehensive_esperanto_text_replacement,
    parallel_process,
    apply_ruby_html_header_and_footer
)
```

- `esp_text_replacement_module.py` から多数の関数を import。  
- 続いて、コード内で

  ```python
  placeholders_for_skipping_replacements = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt')
  placeholders_for_localized_replacement = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换結果捕捉用.txt')
  ```

  などを実行し、**`%...%`スキップ用** と **`@...@`局所置換用** の占位符リストを読み込みます。  
  - これらの占位符 (大量のユニークな文字列) は、大域置換と衝突しないように**一時的に置き換えるため**に使用。  

### 2.4 「並列処理」スイッチの実装

```python
use_parallel = st.checkbox("並列処理を使う", value=False)
num_processes = st.number_input("同時プロセス数", min_value=2, max_value=4, value=4, step=1)
```

- ユーザーがチェックボックスでオン/オフ。  
- `esp_text_replacement_module` の `parallel_process` 関数を呼ぶかどうかをここで決める。

### 2.5 テキストの入力手段とフォーム

```python
source_option = st.radio("入力テキストをどうしますか？", ("手動入力", "ファイルアップロード"))
```

- **「ファイルアップロード」**の場合は `st.file_uploader` で `.txt`等を取り込み → 文字列にデコード  
- **「手動入力」**の場合は `st.text_area` に直接入力  
- Streamlit の `st.form` 構造により、**送信ボタンを押すまでは状態を保持**する実装になっている。

### 2.6 送信ボタン押下時のメイン処理フロー

`submit_btn = st.form_submit_button('送信')` 押下時:

1. **入力テキスト** → `text0`  
2. **「並列処理を使う」** がオンなら  
   ```python
   processed_text = parallel_process(
       text=text0,
       num_processes=num_processes,
       placeholders_for_skipping_replacements=...,
       ...
   )
   ```  
   オフなら  
   ```python
   processed_text = orchestrate_comprehensive_esperanto_text_replacement(
       text=text0,
       ...
   )
   ```  
   いずれも `esp_text_replacement_module.py` 内の関数に丸投げ。

### 2.7 出力文字形式 (上付き/x形式/^形式) の変換

送信後、さらに

```python
if letter_type == '上付き文字':
    processed_text = replace_esperanto_chars(processed_text, x_to_circumflex)
    processed_text = replace_esperanto_chars(processed_text, hat_to_circumflex)
elif letter_type == '^形式':
    processed_text = replace_esperanto_chars(processed_text, x_to_hat)
    processed_text = replace_esperanto_chars(processed_text, circumflex_to_hat)
```

という工程が走る。  
- つまり**置換結果内の「ĉ,ĝ…」をあらためて x形式 / hat形式 に置き換える** (ユーザーが出力形式をどう選んでも対応できるようにするため)。  

### 2.8 結果表示とダウンロード機能

最後に:

```python
processed_text = apply_ruby_html_header_and_footer(processed_text, format_type)

# (プレビュー用に一部省略表示)
# (HTMLの場合は st.tabs(["HTMLプレビュー", ...]) で出力)

st.download_button(
    label="置換結果のダウンロード",
    data=processed_text.encode('utf-8'),
    file_name="置換結果.html",
    mime="text/html"
)
```

- **HTMLプレビュー**には `st.components.v1.html(preview_text, ...)` を使用し、JavaScript が含まれていても概ねレンダリングできます。  
- 最終的に `.html` としてダウンロード。  
  - 「括弧形式」等でも一応 `.html` となっているが、中身がテキストだけの場合は rename しても構わない想定です。

---

## 3. エスペラント文(漢字)置換用のJSONファイル生成ページ.py - 仕組み

### 3.1 このページの役割

- メインアプリ (main.py) に適用する「置換ルール JSON」を**大規模に一括生成**するための補助ページ。  
- ロジックのほとんどは `esp_replacement_json_make_module.py` や一部 `esp_text_replacement_module.py` を利用。

### 3.2 ステップ別の処理 (CSVファイル/JSONファイル 読み込み)

1. **CSVファイルをアップロード or デフォルト使用**  
   - 例: `エスペラント語根-日本語訳ルビ対応リスト.csv` を読み込み、`pd.read_csv(...)` して DataFrame 化。  
     - (usecols=[0,1]) の指定で「最初の2列のみ」を利用。  
2. **「エスペラント単語語根分解法ユーザー設定 JSON」** と **「置換後文字列を追加指定する JSON」** のアップロード/デフォルト選択  
   - これらで**カスタム語根分解**や**カスタム置換**を適用するためのリストをロード。  
   - 例えば `"verbo_s1"` というフラグが付いていたら、動詞活用語尾をまとめて生成する等。

### 3.3 高度な設定 (並列処理)

```python
use_parallel = st.checkbox("並列処理を使う", ...)
num_processes = st.number_input("同時プロセス数", ...)
```

- 大量の語根一覧を**並列で処理**するかどうかの選択。  
- これが後述の `parallel_build_pre_replacements_dict` (esp_replacement_json_make_module.py) を呼ぶときに反映される。

### 3.4 最終的なJSONファイル生成フロー

「置換用JSONファイルを作成する」ボタン押下 → 以下のような大きな流れ:

1. **エスペラント語根の全リスト**(例: `"世界语全部词根_约11137个_202501.txt"` など) をベースに、**仮の「(語根→同じ語根)」置換リスト**を作成し、文字数順にソート → 順番に `safe_replace` で変換  
2. **ユーザーがアップロードした CSV** を使い、(語根→漢字/訳語) の上書きを行う  
3. さらに**カスタム語根分解 JSON** を適用し、追加の派生形(動詞活用など)を含めた置換パターンを生成  
4. **すべてを辞書で保持**して優先順位を付与 (長い語根ほど優先度を高く、単に1文字増えた派生形はさらに加算 etc.)  
5. 最終的に `(old, new, placeholder)` の三要素にまとめた置換リストを3種類  
   - `replacements_final_list` (大域置換)  
   - `replacements_list_for_localized_string` (局所置換)  
   - `replacements_list_for_2char` (2文字語根や接頭/接尾辞向け)  
   を**JSON構造**として格納 → ダウンロード。  

### 3.5 内部的な優先順位計算と辞書の統合

コード中には、たとえば

```python
pre_replacements_dict_3[i]=[j[0], j[2]]
```
のように `(置換対象の単語 -> [置換後文字列, 置換優先順位])` を辞書にどんどん詰め込んでいきます。  
- 同時に**語尾に o/a/e を付与**したり、**動詞活用 as/is/os/us** を付与したりして**文字数を増大 → 優先度を高める**ロジックなどが入り組んでいます。  
- 「語尾 an/on」といった形容詞語尾/名詞語尾の競合を防ぐために、辞書から除外したり追加再生成したりという複雑な処理がある。  
- **最終的には文字数が多いほど先にマッチさせる**ようにすることで、誤置換を防ぎ、より正確な語根分解を可能にしているわけです。

結果的に **replacements_final_list** は非常に大きな配列になり、JSONファイルサイズが数十MB〜に至ることも珍しくありません。

---

## 4. esp_text_replacement_module.py - 主要関数とロジック

このモジュールは「main.py」で使われる**テキスト置換の中核ロジック**を定義しています。

### 4.1 エスペラント文字表記変換 (x形式/hat形式 ⇔ ĉ など)

```python
x_to_circumflex = {...}  # {'cx': 'ĉ', 'gx': 'ĝ', ...}
circumflex_to_x = {...}
x_to_hat = {...}
hat_to_x = {...}
hat_to_circumflex = {...}
circumflex_to_hat = {...}
```

- `replace_esperanto_chars(text, char_dict)` でこれらのマップを順番に適用する。  
- `convert_to_circumflex(text)` は最も代表的な**「c^ / cx」 → 「ĉ」** への統一関数。  

### 4.2 占位符/局所置換/@...@ スキップ/%...% の仕組み

```python
def find_percent_enclosed_strings_for_skipping_replacement(text: str) -> List[str]:
    # %(.{1,50}?)% のような正規表現でマッチ
```
- `%xxx%` 形式を最初に検出してリスト化 → それぞれ**placeholder**に置き換える。  
- 置換後に `%...%` 自体は消え、代わりにランダムに生成されたユニーク文字列(=占位符)が入る。  
- 大域置換が終わった後で**再度元に戻す**流れ。  

同様に `find_at_enclosed_strings_for_localized_replacement` や `create_replacements_list_for_localized_replacement` で  
- `@xxx@` 内を**ローカル置換**(= `replacements_list_for_localized_string`) した上で placeholder に置き換え、  
- 最終的に復元します。  

### 4.3 大域置換 (replacements_final_list) と 2文字語根置換

```python
# 5) 大域置換
valid_replacements = {}
for old, new, placeholder in replacements_final_list:
    if old in text:
        text = text.replace(old, placeholder)
        valid_replacements[placeholder] = new

# 6) 2文字語根置換(2回)
#   2char 用のリストを2回適用する (重複対策)
```

- 大域置換の仕組みは非常にシンプルで、「テキスト内に `old` があれば `placeholder` に置き換え → 後で `placeholder` → `new` に置き換える」二段階法。  
  - これをしないと、たとえば `old = "ama"` を `new="(Amaのルビ)"` に置き換えたあと、さらに「a」としてマッチして予期せぬルビ付けが被る可能性がある。  
  - **一度 placeholder にする**ことで「すでに置換されたテキスト」を保護している。  
- 2文字語根については2回連続で置換している（1回目に登場しなかったものが、2回目に出てくるケースに対応するため）。

### 4.4 最終合成関数 orchestrate_comprehensive_esperanto_text_replacement

```python
def orchestrate_comprehensive_esperanto_text_replacement(...):
    # 1) 半角空白正規化 & エスペラント字上符変換
    # 2) %...% スキップ箇所の占位符化
    # 3) @...@ 局所置換
    # 4) 大域置換 (replacements_final_list)
    # 5) 2文字語根置換
    # 6) placeholder -> 最終文字列に戻す
    # 7) HTML形式なら改行を <br> に
    return text
```

**main.py** のメイン実行部や、**parallel_process** の中で最終的にこの関数を呼び出す。  
流れは前章(4.2,4.3) で述べたステップを順番に実施しているだけ。  
**テキストを一気に処理**したい場合は、この関数が一番重要。

### 4.5 並列処理 (multiprocessing) 周り (parallel_process, process_segment)

```python
def parallel_process(
    text: str,
    num_processes: int,
    ...
) -> str:
    if num_processes <= 1:
        return orchestrate_comprehensive_esperanto_text_replacement(...)

    # 1. 行ごとにテキストを分割
    # 2. ranges を決めて pool.starmap(process_segment, [...]) で並列実行
    # 3. 結合して return
```

- **`parallel_process`** は、行単位でテキストを分割し、`process_segment` に投げるスタイル。  
- スレッドではなく**プロセス**プールを使うため、**`if __name__ == '__main__':`** 等の制約が通常はあるが、streamlit で回避する工夫が冒頭に書いてある。  
- もし**テキストの行数が 1 行しかない**場合は並列化しても意味がないため、その場合はシングルで `orchestrate_comprehensive_esperanto_text_replacement` を使う。  

### 4.6 HTML出力の仕上げ (apply_ruby_html_header_and_footer)

```python
def apply_ruby_html_header_and_footer(processed_text: str, format_type: str) -> str:
    if format_type in ('HTML格式_Ruby文字_大小调整', ...):
        # 大きめの <style> ... </style> と <body> タグを挿入
        # ルビサイズを動的に変える CSS クラスなど
    elif format_type in ('HTML格式', 'HTML格式_汉字替换'):
        # 簡易的に <style>ruby rt { color: blue; }</style>
    else:
        # 何も付けない
```

- `main.py` の最後で `processed_text` にヘッダーやフッターを付与している。  
- ルビのサイズを CSS で制御する仕組みが入り組んでいる。

---

## 5. esp_replacement_json_make_module.py - JSON生成ロジック

JSONファイル生成ページで使用されるモジュール。  
`esp_text_replacement_module.py` とよく似た関数 (名前や機能が重複しているものもある) がある点に留意。

### 5.1 output_format 関数 (HTML/括弧形式など) の詳細

```python
def output_format(main_text, ruby_content, format_type, char_widths_dict):
    if format_type == 'HTML格式_Ruby文字_大小调整':
        # 文字幅を計測 (measure_text_width_Arial16)
        # 親文字とルビ文字の比率に応じて class="XS_S" 等を使い分け
        return f'<ruby>...</ruby>'
    elif format_type == 'HTML格式_Ruby文字_大小调整_汉字替换':
        # 親文字とルビを逆に
    elif format_type == 'HTML格式':
        # シンプルに <ruby>main<rt>ruby</rt></ruby>
    elif format_type == 'HTML格式_汉字替换':
        # 逆に <ruby>ruby<rt>main</rt></ruby>
    elif format_type == '括弧(号)格式':
        return f'{main_text}({ruby_content})'
    elif format_type == '括弧(号)格式_汉字替换':
        return f'{ruby_content}({main_text})'
    else:  # '替换后文字列のみ(仅)保留(简单替换)'
        return ruby_content
```

- **文字幅計測**には `measure_text_width_Arial16` を用い、結果に応じて XS / S / M / L … のクラスを付与しているのが特徴。  
- “漢字とエスペラント語根” がどちらを親文字にするかで複数パターンが存在。

### 5.2 大量のエスペラント語根を辞書化→並列で置換→優先度順にソート

`parallel_build_pre_replacements_dict` や `process_chunk_for_pre_replacements` 関数では  
- **(エスペラント語根, 品詞) のリスト** を分割し、`safe_replace` で CSV や既存ルールを適用して置換した結果を**辞書に蓄える**  
- スレッドセーフな手段で partial_results を集計・マージ  

### 5.3 重複ルビ・大文字化補正などの最終加工

```python
IDENTICAL_RUBY_PATTERN = re.compile(r'<ruby>([^<]+)<rt class="XXL_L">([^<]+)</rt></ruby>')
def remove_redundant_ruby_if_identical(text: str) -> str:
    if group1 == group2:
        return group1
    else:
        return match.group(0)
```

- 親文字とルビ文字が完全に同じ場合は `<ruby>xxx<rt>xxx</rt></ruby>` を単なる `xxx` に戻すなどの処理がある。  
- 大文字化 (capitalize_ruby_and_rt) もあり、**単語先頭文字だけ大文字にする**などの整合性を保っている。

---

## 6. モジュール間連携のまとめ

1. **メインページ(main.py)**  
   - `esp_text_replacement_module.py` を import → 文字列置換の最終関数 (`orchestrate_comprehensive_esperanto_text_replacement`) や 並列処理 (`parallel_process`) を呼び出す。  
   - JSONファイルを読み込んで**「大域置換」「局所置換」「2文字語根置換」**の3リストを取得し、それらをまとめて渡している。  
2. **JSON生成ページ**  
   - `esp_replacement_json_make_module.py` (＋ 一部 `esp_text_replacement_module.py`) を使い、**巨大な replacement リスト**を組み立てた上で JSON化。  
   - CSV → (語根→訳語) → さらに**語根分解 JSON** で派生形を補完 → **最終的に placeholders を含む `(old, new, placeholder)` リストの大量セット**を出力している。  

結果として、**「JSON生成ページ」で作った置換ルール**を**「メインページ」で読み込み適用**する、という流れがアプリ全体の想定運用です。

---

## 7. 補足: multiprocessing.set_start_method("spawn") の背景

Streamlit アプリでは、デフォルトの `fork` を用いる方式でマルチプロセスを起動すると pickle 周りの問題が起こりやすい (PicklingError) 。  
そこで

```python
try:
    multiprocessing.set_start_method("spawn")
except RuntimeError:
    pass
```

としておき、プロセス開始方法を “spawn” に強制しています。  
- Windows や一部環境でも安定して同じ動作をしてくれるため。  
- もし既に start_method が設定済みなら RuntimeError を無視する仕組み。

---

# まとめ

以上が、本アプリ（4つのファイル）それぞれの**コードの仕組み**・**モジュール間連携**・**主要な関数の役割**に関する詳細解説です。

- **大域置換/局所置換/スキップ置換** を重層的に行う仕組み  
- **語根の文字数に基づく優先度付け**や**placeholder の多段階置換**  
- **並列処理 (multiprocessing)**  
- **HTML/CSS を使ったルビ表示**  

など、多岐にわたるロジックが組み合わさっており、最終的にエスペラント文の漢字化やルビを柔軟に実現できるよう設計されています。

ユーザー視点では非常にシンプル(ファイルを選んでボタンを押すだけ)ですが、  
内部では複雑な置換管理を**placeholder**方式で衝突を防ぎつつ実装している、というのが**このアプリ最大のポイント**となります。  

プログラマーの方がソースコードを拡張／改変したり、他の言語・仕組みに転用したりする場合は、

1. 大域置換の優先度コントロール (文字数順ソート etc.)  
2. 2文字語根や接尾辞などへの個別処理  
3. @...@ / %...% の正規表現による事前保護  

などをしっかり把握したうえで改造いただくのが良いでしょう。

これが本アプリ全体の「仕組み」の解説となります。ぜひご参考ください。

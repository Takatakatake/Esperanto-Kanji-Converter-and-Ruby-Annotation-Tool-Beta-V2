import streamlit as st
import multiprocessing

st.title('CPU Core Counter')
st.write('Streamlit Cloudで利用可能なCPUコア数を表示します')

# 論理CPUコア数の取得
logical_cores = multiprocessing.cpu_count()

# 結果表示
st.metric(label="論理CPUコア数", value=logical_cores)

# 注意書き
st.info('''
**注意点**
- Streamlit Cloudの無料ティアでは通常1コアに制限
- 表示される値はホスト環境の物理コア数
- 実際に使用可能なコア数は異なる場合があります
''')
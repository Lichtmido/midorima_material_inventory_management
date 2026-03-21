import streamlit as st
import pandas as pd
from datetime import datetime

# --- 設定 ---
ITEMS = ["銅", "鉄", "鋼鉄", "アルミニウム", "アルミニウム粉末", "メタルスクラップ", "プラスチック", "ガラス", "ゴム", "クリプトスティック"]
USERS = ["緑間理人", "緑間きのこ"]

# SecretsからURLを取得
CSV_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]

# --- データ管理関数 ---
def load_data():
    try:
        # スプレッドシートをCSVとして読み込む
        return pd.read_csv(CSV_URL)
    except Exception:
        # 万が一読み込めない場合は空のデータを作る
        return pd.DataFrame(columns=['日時', '担当者', 'アイテム', 'アクション', '数量'])

def save_data(user, item, action, amount):
    # 書き込みは st-gsheets-connection の機能に頼る（ここが一番エラーが出やすい）
    # もしエラーが続くなら、ここを別の方法に変える必要があります
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = load_data()
    new_data = {
        '日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '担当者': user, 'アイテム': item, 'アクション': action, '数量': amount
    }
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    # 書き込み実行
    conn.update(data=df)

# --- (以下、 get_inventory などの UI部分は前と同じでOK) ---
def get_inventory():
    df = load_data()
    inventory = {item: 0 for item in ITEMS}
    if not df.empty:
        for _, row in df.iterrows():
            if row['アイテム'] in inventory:
                if row['アクション'] == '入手':
                    inventory[row['アイテム']] += row['数量']
                elif row['アクション'] == '売却':
                    inventory[row['アイテム']] -= row['数量']
    return inventory

# --- UI構成 ---
st.set_page_config(page_title="緑間素材店在庫管理", layout="wide")
st.title("📦 緑間素材店リサセン素材在庫管理")

if 'last_user' not in st.session_state: st.session_state.last_user = USERS[0]
if 'last_item' not in st.session_state: st.session_state.last_item = ITEMS[0]

inv = get_inventory()
st.subheader("現在の在庫状況")
cols = st.columns(5)
for i, item in enumerate(ITEMS):
    cols[i % 5].metric(label=item, value=f"{inv[item]} 個")

st.divider()

with st.form("input_form"):
    c1, c2, c3, c4 = st.columns(4)
    with c1: user_input = st.selectbox("担当者", USERS, index=USERS.index(st.session_state.last_user))
    with c2: item_input = st.selectbox("アイテム", ITEMS, index=ITEMS.index(st.session_state.last_item))
    with c3: action_input = st.radio("アクション", ["入手", "売却"], horizontal=True)
    with c4: amount_input = st.number_input("数量", min_value=1, step=1, value=1)
    
    if st.form_submit_button("記録を保存する"):
        if action_input == "売却" and inv[item_input] < amount_input:
            st.error("在庫不足！")
        else:
            save_data(user_input, item_input, action_input, amount_input)
            st.session_state.last_user = user_input
            st.session_state.last_item = item_input
            st.success("保存完了！")
            st.rerun()

import streamlit as st
import pandas as pd
import base64
import requests
from datetime import datetime
from io import StringIO

# --- 設定 ---
ITEMS = ["銅", "鉄", "鋼鉄", "アルミニウム", "アルミニウム粉末", "メタルスクラップ", "プラスチック", "ガラス", "ゴム", "クリプトスティック", "強化プラスチック"]
USERS = ["緑間理人", "緑間きのこ"]

# GitHub連携情報
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_FILE = st.secrets["GITHUB_FILE"]

# --- データ管理関数 (GitHub対応版) ---
def get_github_data():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        content = res.json()
        csv_data = base64.b64decode(content['content']).decode('utf-8-sig')
        df = pd.read_csv(StringIO(csv_data))
        return df, content['sha']
    else:
        # ファイルが存在しない場合は初期ヘッダーで作成
        df_empty = pd.DataFrame(columns=['日時', '担当者', 'アイテム', 'アクション', '数量'])
        return df_empty, None

def save_to_github(df, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')
    
    data = {
        "message": f"Inventory Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": base64.b64encode(csv_content.encode('utf-8-sig')).decode('utf-8'),
    }
    if sha:
        data["sha"] = sha
        
    res = requests.put(url, headers=headers, json=data)
    if res.status_code not in [200, 201]:
        st.error(f"GitHub保存エラー: {res.json().get('message')}")

def load_data():
    df, _ = get_github_data()
    return df

def save_data(user, item, action, amount):
    df, sha = get_github_data()
    new_data = {
        '日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '担当者': user,
        'アイテム': item,
        'アクション': action,
        '数量': amount
    }
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    save_to_github(df, sha)

def delete_row(index):
    df, sha = get_github_data()
    df = df.drop(index)
    save_to_github(df, sha)

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
st.set_page_config(page_title="緑間素材店トランク内在庫管理", layout="wide")
st.title("📦 緑間素材店リサセン素材在庫管理")

# セッション状態の初期化
if 'last_user' not in st.session_state:
    st.session_state.last_user = USERS[0]
if 'last_item' not in st.session_state:
    st.session_state.last_item = ITEMS[0]

# 1. 在庫サマリー表示
st.subheader("現在の在庫状況")
inv = get_inventory()

# 5個ずつに区切って表示する
for i in range(0, len(ITEMS), 5):
    cols = st.columns(5)
    # この5つの列に対して、順番にアイテムを入れていく
    for j in range(5):
        if i + j < len(ITEMS):
            item = ITEMS[i + j]
            cols[j].metric(label=item, value=f"{inv[item]} 個")

st.divider()

# 2. 入力フォーム
st.subheader("新規記録")
with st.form("input_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        user_idx = USERS.index(st.session_state.last_user)
        user_input = st.selectbox("担当者", USERS, index=user_idx)
    with col2:
        item_idx = ITEMS.index(st.session_state.last_item)
        item_input = st.selectbox("アイテム", ITEMS, index=item_idx)
    with col3:
        action_input = st.radio("アクション", ["入手", "売却"], horizontal=True)
    with col4:
        amount_input = st.number_input("数量", min_value=1, step=1, value=1)
    
    submit_button = st.form_submit_button("記録を保存する")

    if submit_button:
        if action_input == "売却" and inv[item_input] < amount_input:
            st.error(f"エラー：{item_input} の在庫が不足しています（現在：{inv[item_input]}個）")
        else:
            save_data(user_input, item_input, action_input, amount_input)
            st.session_state.last_user = user_input
            st.session_state.last_item = item_input
            st.success(f"保存完了！")
            st.rerun()

st.divider()

# 3. 履歴表示と削除機能
st.subheader("📜 最近の在庫変動履歴（直近20件）")
df_history = load_data()

if df_history.empty:
    st.info("履歴はまだありません。")
else:
    df_recent = df_history.iloc[::-1].head(20)
    last_5_indices = df_history.index[-5:]
    
    for idx, row in df_recent.iterrows():
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([3, 2, 2, 1, 1, 2])
        h_col1.write(row['日時'])
        h_col2.write(row['担当者'])
        h_col3.write(row['アイテム'])
        h_col4.write(row['アクション'])
        h_col5.write(f"{row['数量']}個")
        
        if idx in last_5_indices:
            if h_col6.button("取り消す", key=f"del_{idx}"):
                delete_row(idx)
                st.rerun()
        else:
            h_col6.write("---")

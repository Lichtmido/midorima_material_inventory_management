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

# 追記：一括保存用
def save_bulk_data(user, cart_items):
    df, sha = get_github_data()
    rows = []
    for item in cart_items:
        rows.append({
            '日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '担当者': user,
            'アイテム': item['name'],
            'アクション': item['action'],
            '数量': item['amount']
        })
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    save_to_github(df, sha)

def delete_row(index):
    df, sha = get_github_data()
    df = df.drop(index)
    save_to_github(df, sha)

def get_inventory(filter_user=None):
    df = load_data()
    inventory = {item: 0 for item in ITEMS}
    if not df.empty:
        if filter_user:
            target_df = df[df['担当者'] == filter_user]
        else:
            target_df = df
            
        for _, row in target_df.iterrows():
            if row['アイテム'] in inventory:
                if row['アクション'] == '入手':
                    inventory[row['アイテム']] += row['数量']
                elif row['アクション'] == '売却':
                    inventory[row['アイテム']] -= row['数量']
    return inventory

# --- UI構成 ---
st.set_page_config(page_title="緑間素材店トランク内在庫管理", layout="wide")
st.title("📦 緑間素材店 在庫管理 & 複数査定システム")

# セッション状態の初期化
if 'last_user' not in st.session_state:
    st.session_state.last_user = USERS[0]
if 'last_item' not in st.session_state:
    st.session_state.last_item = ITEMS[0]
if 'cart' not in st.session_state:
    st.session_state.cart = []

# 現在の総在庫を取得
total_inv = get_inventory()

# --- 🆕 追加：マルチ査定カートセクション ---
st.header("⚖️ 販売・買取 マルチ査定カート")
with st.container(border=True):
    calc_col1, calc_col2, calc_col3, calc_col4 = st.columns([1.5, 2, 2, 2])
    with calc_col1:
        trade_mode = st.radio("取引種別", ["販売(売却)", "買取(入手)"], horizontal=False, key="trade_mode")
    with calc_col2:
        calc_item = st.selectbox("査定アイテム", ITEMS, key="calc_item")
        st.caption(f"現在の総在庫: {total_inv[calc_item]} 個")
    with calc_col3:
        market_price = st.number_input("単価 (円)", min_value=0, value=1000, step=100, key="market_price")
    with calc_col4:
        calc_amount = st.number_input("数量", min_value=1, value=1, step=1, key="calc_amount")

    if st.button("➕ カートに追加"):
        # 在庫チェック（販売時のみ）
        action_label = "売却" if trade_mode == "販売(売却)" else "入手"
        already_in_cart = sum(item['amount'] for item in st.session_state.cart if item['name'] == calc_item and item['action'] == "売却")
        
        if action_label == "売却" and total_inv[calc_item] < (calc_amount + already_in_cart):
            st.error(f"在庫不足です！ (トランク残量: {total_inv[calc_item]}個)")
        else:
            st.session_state.cart.append({
                "name": calc_item,
                "price": market_price,
                "amount": calc_amount,
                "subtotal": market_price * calc_amount,
                "action": action_label
            })
            st.toast(f"{calc_item} をカートに追加しました")

# カートの中身表示
if st.session_state.cart:
    total_bill = 0
    receipt_details = []
    
    st.subheader("📝 査定リスト")
    for i, item in enumerate(st.session_state.cart):
        c_a, c_b, c_c, c_d, c_e = st.columns([2, 2, 2, 2, 0.5])
        c_a.write(f"**{item['name']}** ({item['action']})")
        c_b.write(f"{item['price']:,} 円 × {item['amount']}個")
        c_c.write(f"小計: {item['subtotal']:,} 円")
        total_bill += item['subtotal']
        receipt_details.append(f"{item['name']}x{item['amount']}(@{item['price']:,})")
        if c_e.button("🗑️", key=f"cart_rm_{i}"):
            st.session_state.cart.pop(i)
            st.rerun()
    
    st.divider()
    st.markdown(f"### 💰 合計金額: **{total_bill:,} 円**")
    
    # コピー用テキスト
    full_receipt = f"【緑間素材店 査定】合計:{total_bill:,}円 / 内訳:" + " | ".join(receipt_details)
    st.text_input("チャット用コピー", value=full_receipt)
    
    # 一括反映
    res_user = st.radio("取引担当者", USERS, horizontal=True, key="res_user")
    col_f1, col_f2 = st.columns([1, 4])
    if col_f1.button("🚀 取引確定・在庫反映"):
        save_bulk_data(res_user, st.session_state.cart)
        st.session_state.cart = []
        st.success("一括保存しました！")
        st.rerun()
    if col_f2.button("🛒 カートを空にする"):
        st.session_state.cart = []
        st.rerun()
else:
    st.info("査定カートは空です。上のフォームからアイテムを追加してください。")

st.divider()

# --- 既存の在庫表示セクション ---
view_mode = st.radio("表示モード", ["合計在庫", "緑間理人の入手分", "緑間きのこの入手分"], horizontal=True)

if view_mode == "緑間理人の入手分":
    inv = get_inventory(filter_user="緑間理人")
    st.subheader("📊 緑間理人の現在の所持・入手状況")
elif view_mode == "緑間きのこの入手分":
    inv = get_inventory(filter_user="緑間きのこ")
    st.subheader("📊 緑間きのこの現在の所持・入手状況")
else:
    inv = total_inv
    st.subheader("📊 現在の総在庫状況")

# 1. 在庫サマリー表示
for i in range(0, len(ITEMS), 5):
    cols = st.columns(5)
    for j in range(5):
        if i + j < len(ITEMS):
            item = ITEMS[i + j]
            cols[j].metric(label=item, value=f"{inv[item]} 個")

st.divider()

# 2. 既存の新規記録（手動調整用）
st.subheader("新規記録 (手動調整)")
with st.form("input_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        user_idx = USERS.index(st.session_state.last_user)
        user_input = st.selectbox("担当者", USERS, index=user_idx, key="manual_user")
    with col2:
        item_idx = ITEMS.index(st.session_state.last_item)
        item_input = st.selectbox("アイテム", ITEMS, index=item_idx, key="manual_item")
    with col3:
        action_input = st.radio("アクション", ["入手", "売却"], horizontal=True, key="manual_action")
    with col4:
        amount_input = st.number_input("数量", min_value=1, step=1, value=1, key="manual_amount")
    
    submit_button = st.form_submit_button("記録を保存する")

    if submit_button:
        current_total_inv = get_inventory()
        if action_input == "売却" and current_total_inv[item_input] < amount_input:
            st.error(f"エラー：全体在庫の {item_input} が不足しています（現在：{current_total_inv[item_input]}個）")
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

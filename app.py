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
    new_data = {'日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '担当者': user, 'アイテム': item, 'アクション': action, '数量': amount}
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    save_to_github(df, sha)

def save_bulk_data(user, cart_items):
    df, sha = get_github_data()
    rows = []
    for item in cart_items:
        rows.append({'日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '担当者': user, 'アイテム': item['name'], 'アクション': item['action'], '数量': item['amount']})
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
        target_df = df[df['担当者'] == filter_user] if filter_user else df
        for _, row in target_df.iterrows():
            if row['アイテム'] in inventory:
                if row['アクション'] == '入手': inventory[row['アイテム']] += row['数量']
                elif row['アクション'] == '売却': inventory[row['アイテム']] -= row['数量']
    return inventory

# --- UI構成 ---
st.set_page_config(page_title="緑間素材店トランク内在庫管理", layout="wide")
st.title("📦 緑間素材店 在庫管理システム")

# セッション状態の初期化
if 'last_user' not in st.session_state: st.session_state.last_user = USERS[0]
if 'last_item' not in st.session_state: st.session_state.last_item = ITEMS[0]
if 'cart' not in st.session_state: st.session_state.cart = []
if 'prices' not in st.session_state: st.session_state.prices = {item: 1000 for item in ITEMS}

total_inv = get_inventory()

# ==========================================
# 1. 在庫表示セクション (メイン)
# ==========================================
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

for i in range(0, len(ITEMS), 6):
    cols = st.columns(6)
    for j in range(6):
        if i + j < len(ITEMS):
            item = ITEMS[i + j]
            cols[j].metric(label=item, value=f"{inv[item]} 個")

st.divider()

# ==========================================
# 2. 既存の新規記録フォーム (トランク出し入れ用)
# ==========================================
st.subheader("新規記録 (トランク出し入れ)")
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
        if action_input == "売却" and total_inv[item_input] < amount_input:
            st.error(f"エラー：全体在庫の {item_input} が不足しています（現在：{total_inv[item_input]}個）")
        else:
            save_data(user_input, item_input, action_input, amount_input)
            st.session_state.last_user, st.session_state.last_item = user_input, item_input
            st.success(f"保存完了！")
            st.rerun()

st.divider()

# ==========================================
# 3. 販売・査定セクション (下部へ配置)
# ==========================================
st.header("⚖️ 販売・買取 査定システム")

# --- 一括単価反映機能 ---
with st.expander("💰 単価の一括設定"):
    st.info("アイテム,単価 の形式で貼り付けてください (例: 銅,2000)")
    bulk_price_text = st.text_area("一括入力エリア", height=150)
    if st.button("単価を反映する"):
        updated_prices = st.session_state.prices.copy()
        for line in bulk_price_text.split('\n'):
            if ',' in line:
                parts = line.split(',')
                name, price = parts[0].strip(), parts[1].strip()
                if name in ITEMS and price.isdigit():
                    updated_prices[name] = int(price)
        st.session_state.prices = updated_prices
        st.success("単価リストを更新しました！")

# --- カート入力 ---
with st.container(border=True):
    calc_col1, calc_col2, calc_col3, calc_col4 = st.columns([1.5, 2, 2, 2])
    with calc_col1:
        trade_mode = st.radio("取引種別", ["販売(売却)", "買取(入手)"], horizontal=False, key="trade_mode")
    with calc_col2:
        calc_item = st.selectbox("査定アイテム", ITEMS, key="calc_item")
        st.caption(f"トランク在庫: {total_inv[calc_item]} 個 / 現在設定単価: {st.session_state.prices[calc_item]:,}円")
    with calc_col3:
        # 一括設定された単価をデフォルト値として表示
        m_price = st.number_input("単価 (円)", min_value=0, value=st.session_state.prices[calc_item], step=100, key="m_price")
    with calc_col4:
        c_amount = st.number_input("数量", min_value=1, value=1, step=1, key="c_amount")

    if st.button("➕ カートに追加"):
        act_label = "売却" if trade_mode == "販売(売却)" else "入手"
        already_in = sum(item['amount'] for item in st.session_state.cart if item['name'] == calc_item and item['action'] == "売却")
        if act_label == "売却" and total_inv[calc_item] < (c_amount + already_in):
            st.error("在庫不足です！")
        else:
            st.session_state.cart.append({"name": calc_item, "price": m_price, "amount": c_amount, "subtotal": m_price * c_amount, "action": act_label})
            st.rerun()

# カート表示
if st.session_state.cart:
    total_bill, receipt_details = 0, []
    st.subheader("📝 査定リスト")
    for i, item in enumerate(st.session_state.cart):
        ca, cb, cc, ce = st.columns([2, 2, 2, 0.5])
        ca.write(f"**{item['name']}** ({item['action']})")
        cb.write(f"{item['price']:,}円 × {item['amount']}個")
        cc.write(f"小計: {item['subtotal']:,}円")
        total_bill += item['subtotal']
        receipt_details.append(f"{item['name']}x{item['amount']}(@{item['price']:,})")
        if ce.button("🗑️", key=f"cart_rm_{i}"):
            st.session_state.cart.pop(i); st.rerun()
    st.divider()
    st.markdown(f"### 💰 合計請求金額: **{total_bill:,} 円**")
    st.text_input("チャット用コピー", value=f"【緑間素材店 査定】合計:{total_bill:,}円 / 内訳:" + " | ".join(receipt_details))
    res_user = st.radio("取引担当者", USERS, horizontal=True, key="res_user")
    if st.button("🚀 取引を確定して在庫を反映"):
        save_bulk_data(res_user, st.session_state.cart)
        st.session_state.cart = []; st.success("一括保存完了！"); st.rerun()

st.divider()

# ==========================================
# 4. 履歴表示 (以前のまま)
# ==========================================
st.subheader("📜 最近の在庫変動履歴（直近20件）")
df_history = load_data()
if not df_history.empty:
    df_recent = df_history.iloc[::-1].head(20)
    last_5_indices = df_history.index[-5:]
    for idx, row in df_recent.iterrows():
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([3, 2, 2, 1, 1, 2])
        h_col1.write(row['日時']); h_col2.write(row['担当者']); h_col3.write(row['アイテム']); h_col4.write(row['アクション']); h_col5.write(f"{row['数量']}個")
        if idx in last_5_indices:
            if h_col6.button("取り消す", key=f"del_{idx}"): delete_row(idx); st.rerun()
        else: h_col6.write("---")

import streamlit as st
import requests
import base64
import json
import pytz
from datetime import datetime, time

# --- AUTHENTICATION (PASSWORD CHECK) ---
def check_password():
    """Returns `True` if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Show input for password
    st.title("🔒 Login Required")
    pwd = st.text_input("Enter Password", type="password", key="pwd_input")
    
    # Check against Secrets
    if st.button("Log In"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Wrong password")
    return False

if not check_password():
    st.stop()  # Stop here if not logged in

# --- MAIN APP STARTS HERE ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_OWNER = st.secrets["github"]["owner"]
    GITHUB_REPO = st.secrets["github"]["repo"]
except Exception:
    st.error("❌ Secrets not found!")
    st.stop()

FILE_PATH = "scheduled_posts.json"
BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def get_data():
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content) if content.strip() else [], data["sha"]
    return [], None

def save_data(posts, sha):
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    content = base64.b64encode(json.dumps(posts, indent=2).encode("utf-8")).decode("utf-8")
    body = {"message": "Update schedule", "content": content, "sha": sha}
    resp = requests.put(url, headers=HEADERS, json=body)
    return resp.status_code in [200, 201]

st.set_page_config(page_title="X Pro Scheduler", page_icon="🇵🇰")
st.title("🇵🇰 X Pro Scheduler (PKT)")

posts, sha = get_data()
pkt_zone = pytz.timezone('Asia/Karachi')
utc_zone = pytz.utc

with st.expander("➕ Add New Post", expanded=True):
    with st.form("add_post"):
        text = st.text_area("Tweet Content (Max 280)", max_chars=280)
        st.write("**Schedule Time (Pakistan Standard Time):**")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        date_val = c1.date_input("Date")
        hour_val = c2.selectbox("Hour", range(1, 13))
        min_val = c3.selectbox("Minute", range(0, 60))
        ampm_val = c4.selectbox("AM/PM", ["AM", "PM"])

        if st.form_submit_button("Schedule Post"):
            if not text:
                st.warning("⚠️ Text cannot be empty.")
            else:
                hour_24 = hour_val
                if ampm_val == "PM" and hour_val != 12: hour_24 += 12
                if ampm_val == "AM" and hour_val == 12: hour_24 = 0
                dt_naive = datetime.combine(date_val, time(hour_24, min_val))
                dt_pkt = pkt_zone.localize(dt_naive)
                dt_utc = dt_pkt.astimezone(utc_zone)
                
                posts.append({"text": text, "schedule_time": dt_utc.isoformat()})
                if save_data(posts, sha):
                    st.success("✅ Scheduled!")
                    st.rerun()
                else:
                    st.error("Failed to save.")

st.subheader(f"Queue ({len(posts)})")
if posts:
    posts.sort(key=lambda x: x['schedule_time'])
    for i, p in enumerate(posts):
        dt_utc = datetime.fromisoformat(p['schedule_time'])
        dt_pkt_display = dt_utc.astimezone(pkt_zone)
        display_str = dt_pkt_display.strftime('%Y-%m-%d %I:%M %p')
        with st.container(border=True):
            st.markdown(f"⏳ **{display_str} PKT**")
            st.text(p['text'])
            if st.button("🗑️ Delete", key=f"del_{i}"):
                posts.pop(i)
                save_data(posts, sha)
                st.rerun()
else:
    st.info("No posts in queue.")

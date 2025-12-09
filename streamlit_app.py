import streamlit as st
import requests
import base64
import json
from datetime import datetime, timezone

# --- CONFIGURATION ---
# Uses Streamlit Secrets (Works on Cloud)
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_OWNER = st.secrets["github"]["owner"]
    GITHUB_REPO = st.secrets["github"]["repo"]
except Exception:
    st.error("❌ Secrets not found! If running locally, make sure you have .streamlit/secrets.toml")
    st.stop()

FILE_PATH = "scheduled_posts.json"
BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# --- FUNCTIONS ---
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

# --- UI LAYOUT ---
st.set_page_config(page_title="X Scheduler", page_icon="🐦")
st.title("🐦 X (Twitter) Auto-Scheduler")

# 1. Show Current Posts
posts, sha = get_data()

with st.expander("➕ Add New Post", expanded=True):
    with st.form("add_post"):
        text = st.text_area("Tweet Content (Max 280)", max_chars=280)
        c1, c2 = st.columns(2)
        date = c1.date_input("Date")
        time = c2.time_input("Time (UTC)")
        if st.form_submit_button("Schedule"):
            dt = datetime.combine(date, time).replace(tzinfo=timezone.utc)
            posts.append({"text": text, "schedule_time": dt.isoformat()})
            if save_data(posts, sha):
                st.success("Scheduled!")
                st.rerun()
            else:
                st.error("Failed to save.")

st.subheader(f"Queue ({len(posts)})")
if posts:
    # Sort by time
    posts.sort(key=lambda x: x['schedule_time'])
    for i, p in enumerate(posts):
        dt = datetime.fromisoformat(p['schedule_time'])
        is_past = dt < datetime.now(timezone.utc)
        status_icon = "⚠️ OVERDUE" if is_past else "⏳ Upcoming"
        
        with st.container(border=True):
            st.markdown(f"**{status_icon}:** `{dt.strftime('%Y-%m-%d %H:%M UTC')}`")
            st.text(p['text'])
            if st.button("🗑️ Delete", key=f"del_{i}"):
                posts.pop(i)
                save_data(posts, sha)
                st.rerun()
else:
    st.info("No posts in queue.")
import streamlit as st
import requests
import base64
import json
import pytz
from datetime import datetime, time

# --- CONFIGURATION ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_OWNER = st.secrets["github"]["owner"]
    GITHUB_REPO = st.secrets["github"]["repo"]
except Exception:
    st.error("❌ Secrets not found! Please check Streamlit Cloud Settings.")
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
st.set_page_config(page_title="X Pro Scheduler", page_icon="🇵🇰")
st.title("🇵🇰 X Pro Scheduler (PKT)")

posts, sha = get_data()

# TIMEZONES
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
                # 1. Convert 12h AM/PM to 24h
                hour_24 = hour_val
                if ampm_val == "PM" and hour_val != 12:
                    hour_24 += 12
                if ampm_val == "AM" and hour_val == 12:
                    hour_24 = 0

                # 2. Create Naive Datetime
                dt_naive = datetime.combine(date_val, time(hour_24, min_val))

                # 3. Make it "Aware" (Label it as Pakistan Time)
                dt_pkt = pkt_zone.localize(dt_naive)

                # 4. Convert to UTC (For the Server)
                dt_utc = dt_pkt.astimezone(utc_zone)

                posts.append({"text": text, "schedule_time": dt_utc.isoformat()})

                if save_data(posts, sha):
                    st.success(f"✅ Scheduled for {hour_val}:{min_val:02d} {ampm_val} PKT")
                    st.rerun()
                else:
                    st.error("Failed to save.")

st.subheader(f"Queue ({len(posts)})")
if posts:
    posts.sort(key=lambda x: x['schedule_time'])
    for i, p in enumerate(posts):
        # Read UTC time from file
        dt_utc = datetime.fromisoformat(p['schedule_time'])

        # Convert UTC back to PKT for Display
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



# import streamlit as st
# import requests
# import base64
# import json
# from datetime import datetime, timezone

# # --- CONFIGURATION ---
# # Uses Streamlit Secrets (Works on Cloud)
# try:
#     GITHUB_TOKEN = st.secrets["github"]["token"]
#     GITHUB_OWNER = st.secrets["github"]["owner"]
#     GITHUB_REPO = st.secrets["github"]["repo"]
# except Exception:
#     st.error("❌ Secrets not found! If running locally, make sure you have .streamlit/secrets.toml")
#     st.stop()

# FILE_PATH = "scheduled_posts.json"
# BASE_URL = "https://api.github.com"
# HEADERS = {
#     "Authorization": f"Bearer {GITHUB_TOKEN}",
#     "Accept": "application/vnd.github+json",
#     "X-GitHub-Api-Version": "2022-11-28"
# }

# # --- FUNCTIONS ---
# def get_data():
#     url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
#     resp = requests.get(url, headers=HEADERS)
#     if resp.status_code == 200:
#         data = resp.json()
#         content = base64.b64decode(data["content"]).decode("utf-8")
#         return json.loads(content) if content.strip() else [], data["sha"]
#     return [], None

# def save_data(posts, sha):
#     url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
#     content = base64.b64encode(json.dumps(posts, indent=2).encode("utf-8")).decode("utf-8")
#     body = {"message": "Update schedule", "content": content, "sha": sha}
#     resp = requests.put(url, headers=HEADERS, json=body)
#     return resp.status_code in [200, 201]

# # --- UI LAYOUT ---
# st.set_page_config(page_title="X Scheduler", page_icon="🐦")
# st.title("🐦 X (Twitter) Auto-Scheduler")

# # 1. Show Current Posts
# posts, sha = get_data()

# with st.expander("➕ Add New Post", expanded=True):
#     with st.form("add_post"):
#         text = st.text_area("Tweet Content (Max 280)", max_chars=280)
#         c1, c2 = st.columns(2)
#         date = c1.date_input("Date")
#         time = c2.time_input("Time (UTC)")
#         if st.form_submit_button("Schedule"):
#             dt = datetime.combine(date, time).replace(tzinfo=timezone.utc)
#             posts.append({"text": text, "schedule_time": dt.isoformat()})
#             if save_data(posts, sha):
#                 st.success("Scheduled!")
#                 st.rerun()
#             else:
#                 st.error("Failed to save.")

# st.subheader(f"Queue ({len(posts)})")
# if posts:
#     # Sort by time
#     posts.sort(key=lambda x: x['schedule_time'])
#     for i, p in enumerate(posts):
#         dt = datetime.fromisoformat(p['schedule_time'])
#         is_past = dt < datetime.now(timezone.utc)
#         status_icon = "⚠️ OVERDUE" if is_past else "⏳ Upcoming"
        
#         with st.container(border=True):
#             st.markdown(f"**{status_icon}:** `{dt.strftime('%Y-%m-%d %H:%M UTC')}`")
#             st.text(p['text'])
#             if st.button("🗑️ Delete", key=f"del_{i}"):
#                 posts.pop(i)
#                 save_data(posts, sha)
#                 st.rerun()
# else:
#     st.info("No posts in queue.")
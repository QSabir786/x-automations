import streamlit as st
import tweepy
import os
from dotenv import load_dotenv

# --- 1. BACKEND SETUP (Load Keys) ---
# This looks for the .env file in the same folder
load_dotenv()

# Retrieve keys from the loaded .env file
CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# --- 2. UI LAYOUT ---
st.set_page_config(page_title="Local X Poster", page_icon="🐦")
st.title("🐦 Simple X Poster (Local Mode)")

# Quick check to ensure keys are actually found
if not CONSUMER_KEY:
    st.error("❌ Error: API Keys not found. Please check your .env file.")
    st.stop()
else:
    st.caption("✅ Connected to .env file")

# Input Area
tweet_text = st.text_area("Write your tweet here:", height=100, max_chars=280)

# --- 3. LOGIC (The "Post" Action) ---
if st.button("🚀 Post to X Now", type="primary"):
    if not tweet_text.strip():
        st.warning("⚠️ Text cannot be empty.")
    else:
        try:
            # Initialize Client (The backend part)
            client = tweepy.Client(
                consumer_key=CONSUMER_KEY,
                consumer_secret=CONSUMER_SECRET,
                access_token=ACCESS_TOKEN,
                access_token_secret=ACCESS_TOKEN_SECRET
            )
            
            # Send the Tweet
            response = client.create_tweet(text=tweet_text)
            
            # Show Success
            st.success(f"✅ Success! Tweet sent.")
            st.code(f"Tweet ID: {response.data['id']}")
            
        except Exception as e:
            st.error(f"❌ Failed to post: {e}")






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
import streamlit as st
import requests
import base64
import json
import pytz
from datetime import datetime, time, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# --- PAGE CONFIG ---
st.set_page_config(page_title="X Command Center", page_icon="🇵🇰", layout="wide")
st.title("🇵🇰 X Command Center")

# --- AUTH & SETUP ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_OWNER = st.secrets["github"]["owner"]
    GITHUB_REPO = st.secrets["github"]["repo"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("❌ Secrets missing! Check Streamlit Settings.")
    st.stop()

# Initialize Session State for the Text Box
if "tweet_content" not in st.session_state:
    st.session_state.tweet_content = ""

# --- FUNCTIONS ---
def get_ai_tweet(title, url):
    """Uses Gemini 2.5 Flash to write a tweet."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", # Flash is fast & free tier compatible
        google_api_key=GOOGLE_API_KEY,
        temperature=0.7
    )

    template = """
    You are a professional social media manager.
    Write a viral, engaging tweet about this news story.

    Headline: {title}
    Link: {url}

    Rules:
    - Must be under 280 characters.
    - Use 2-3 relevant hashtags.
    - Be punchy and exciting.
    - Do NOT start with "Here is a tweet". Just give the text.
    """

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    return chain.invoke({"title": title, "url": url}).content

def fetch_news(topic):
    url = f"https://newsapi.org/v2/everything?q={topic}&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    try:
        resp = requests.get(url)
        data = resp.json()
        return data.get("articles", [])[:5] # Get top 5
    except:
        return []

def get_github_data():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/scheduled_posts.json"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content) if content.strip() else [], data["sha"]
    return [], None

def save_to_github(posts, sha):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/scheduled_posts.json"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    content = base64.b64encode(json.dumps(posts, indent=2).encode("utf-8")).decode("utf-8")
    body = {"message": "Update schedule", "content": content, "sha": sha}
    requests.put(url, headers=headers, json=body)

# --- LAYOUT ---
col_scheduler, col_news = st.columns([1, 1]) # Split screen 50/50

# ==========================
# RIGHT COLUMN: NEWS HUNTER
# ==========================
with col_news:
    st.subheader("🕵️ AI News Hunter")
    topic = st.text_input("Search Topic", value="Artificial Intelligence")

    if st.button("🔎 Fetch News"):
        news_items = fetch_news(topic)
        st.session_state.news_cache = news_items # Save to keep them on screen

    if "news_cache" in st.session_state:
        for article in st.session_state.news_cache:
            with st.container(border=True):
                st.markdown(f"**{article['title']}**")
                st.caption(f"Source: {article['source']['name']}")

                # THE MAGIC BUTTON
                if st.button("✨ Generate Tweet", key=article['url']):
                    with st.spinner("Gemini is writing..."):
                        generated_text = get_ai_tweet(article['title'], article['url'])
                        st.session_state.tweet_content = generated_text # Teleport text to left column
                        st.rerun() # Refresh page to show text

# ==========================
# LEFT COLUMN: SCHEDULER
# ==========================
with col_scheduler:
    st.subheader("📅 Scheduler")

    posts, sha = get_github_data()
    pkt_zone = pytz.timezone('Asia/Karachi')
    utc_zone = pytz.utc

    with st.form("schedule_form", clear_on_submit=True):
        # The value comes from Session State (Auto-filled by Gemini)
        text_input = st.text_area("Tweet Content", value=st.session_state.tweet_content, height=150, max_chars=280)

        st.write("**Schedule Time (PKT)**")
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        date_val = c1.date_input("Date")
        hour_val = c2.selectbox("Hour", range(1, 13))
        min_val = c3.selectbox("Minute", range(0, 60))
        ampm = c4.selectbox("AM/PM", ["AM", "PM"])

        if st.form_submit_button("🚀 Schedule Post"):
            if not text_input:
                st.warning("Write something first!")
            else:
                # Time conversion logic
                h24 = hour_val
                if ampm == "PM" and hour_val != 12: h24 += 12
                if ampm == "AM" and hour_val == 12: h24 = 0

                dt_naive = datetime.combine(date_val, time(h24, min_val))
                dt_pkt = pkt_zone.localize(dt_naive)
                dt_utc = dt_pkt.astimezone(utc_zone)

                posts.append({"text": text_input, "schedule_time": dt_utc.isoformat()})
                save_to_github(posts, sha)

                # Clear the box after saving
                st.session_state.tweet_content = ""
                st.success("Scheduled!")
                st.rerun()

    st.divider()
    st.write(f"**Queue ({len(posts)}):**")
    # Show queue logic (Simplified for space)
    for i, p in enumerate(posts):
        dt = datetime.fromisoformat(p['schedule_time']).astimezone(pkt_zone)
        with st.expander(f"{dt.strftime('%I:%M %p')} - {p['text'][:30]}..."):
            st.text(p['text'])
            if st.button("Delete", key=f"d_{i}"):
                posts.pop(i)
                save_to_github(posts, sha)
                st.rerun()


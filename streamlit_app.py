import streamlit as st
import requests
import base64
import json
import pytz
import feedparser
import random
from datetime import datetime, time, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# --- PAGE CONFIG ---
st.set_page_config(page_title="Agency Command Center", page_icon="🇵🇰", layout="wide")

# --- AUTHENTICATION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    st.markdown("## 🔒 Login Required")
    pwd = st.text_input("Enter Password", type="password")
    if st.button("Log In"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Wrong password")
    return False

if not check_password():
    st.stop()

# --- SETUP KEYS ---
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_OWNER = st.secrets["github"]["owner"]
    GITHUB_REPO = st.secrets["github"]["repo"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    # NewsAPI Key removed (We use Reddit now)
except Exception:
    st.error("❌ Secrets missing! Check Streamlit Settings.")
    st.stop()

# Initialize Session State
if "tweet_content" not in st.session_state: st.session_state.tweet_content = ""
if "page_selection" not in st.session_state: st.session_state.page_selection = "Post Scheduler"
if "lead_gen_suggestions" not in st.session_state: st.session_state.lead_gen_suggestions = []
if "news_cache" not in st.session_state: st.session_state.news_cache = []

# --- HELPER FUNCTIONS ---

def get_gemini_model(temp=0.7):
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=temp
    )

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

def switch_to_scheduler(text):
    """Teleports text to the scheduler page."""
    st.session_state.tweet_content = text
    st.session_state.page_selection = "Post Scheduler"
    st.rerun()

# --- NEW: REDDIT TECH NEWS FETCHER ---
def fetch_reddit_tech_news():
    """Fetches trending tech news from Reddit RSS."""
    # Focusing on News & Future Tech
    rss_url = "https://www.reddit.com/r/technology+gadgets+Futurology+ArtificialIntelligence/top.rss?t=day&limit=30"
    
    try:
        feed = feedparser.parse(rss_url)
        entries = feed.entries
        random.shuffle(entries) # Shuffle for freshness
        
        posts = []
        for entry in entries[:10]:
            posts.append({
                "title": entry.title,
                "link": entry.link,
                "source": "Reddit Tech"
            })
        return posts
    except Exception as e:
        st.error(f"RSS Error: {e}")
        return []

# --- REDDIT VIRAL FETCHER (LEAD GEN) ---
def fetch_reddit_viral():
    """Fetches viral discussions for Lead Gen."""
    rss_url = "https://www.reddit.com/r/SaaS+Entrepreneur+Marketing+OpenAI/top.rss?t=week&limit=50"
    try:
        feed = feedparser.parse(rss_url)
        entries = feed.entries
        random.shuffle(entries)
        posts = []
        for entry in entries[:15]:
            posts.append(f"Title: {entry.title}\nLink: {entry.link}")
        return posts
    except Exception as e:
        return []

# --- AI GENERATORS ---

def generate_10_lead_posts(reddit_data):
    """Generates 10 Lead Gen Tweets with STRICT LIMITS."""
    llm = get_gemini_model(temp=0.8)
    
    template = """
    You are a Viral Social Media Ghostwriter.
    Analyze these Reddit discussions and write 10 "Lead Gen" tweets.
    
    CRITICAL RULES:
    1. LENGTH: Every tweet MUST be under 280 characters. NO EXCEPTIONS.
    2. HASHTAGS: Every tweet MUST end with 2-3 viral hashtags (e.g., #SaaS #AI #Growth).
    3. TONE: Punchy, "No-BS", controversial or insightful.
    4. FORMAT: Hook -> Problem -> Solution -> CTA.
    
    INPUT DATA:
    {reddit_data}
    
    OUTPUT FORMAT (JSON ONLY):
    [
      {{"topic": "Growth", "tweet": "Your tweet here... #SaaS #Growth", "source": "Reddit Title"}}
    ]
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    context = "\n\n".join(reddit_data) 
    return chain.invoke({"reddit_data": context})

def generate_news_tweet(title, url):
    """Generates a Tech News Tweet."""
    llm = get_gemini_model(temp=0.5)
    template = """
    You are a Tech Reporter. Write a tweet about this news.
    Headline: {title}
    Link: {url}
    
    Rules:
    - STRICTLY under 280 characters.
    - Include link.
    - End with 2 relevant hashtags (e.g. #TechNews #AI).
    - No emojis.
    """
    prompt = ChatPromptTemplate.from_template(template)
    return prompt | llm | (lambda x: x.invoke({"title": title, "url": url}).content)

# --- NAVIGATION ---
st.sidebar.title("🚀 Agency Panel")
selection = st.sidebar.radio("Go to:", ["Post Scheduler", "Lead Gen (Viral)", "Tech News (Reddit)"], key="nav_radio")

if st.session_state.page_selection != selection:
    st.session_state.page_selection = selection
    st.rerun()

# --- PAGE 1: POST SCHEDULER ---
if selection == "Post Scheduler":
    st.title("📅 Post Scheduler")
    
    posts, sha = get_github_data()
    pkt_zone = pytz.timezone('Asia/Karachi')
    utc_zone = pytz.utc

    with st.form("schedule_form", clear_on_submit=True):
        text_input = st.text_area("Tweet Content", value=st.session_state.tweet_content, height=150, max_chars=280)
        
        # --- NEW: IMAGE UPLOADER ---
        uploaded_file = st.file_uploader("📷 Attach Image (Optional)", type=["png", "jpg", "jpeg"])
        
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
                h24 = hour_val
                if ampm == "PM" and hour_val != 12: h24 += 12
                if ampm == "AM" and hour_val == 12: h24 = 0
                
                dt_naive = datetime.combine(date_val, time(h24, min_val))
                dt_pkt = pkt_zone.localize(dt_naive)
                dt_utc = dt_pkt.astimezone(utc_zone)
                
                # Handle Image Logic (Convert to Base64 for storage)
                image_data = None
                if uploaded_file is not None:
                    # Warning: Large images can slow down the repo!
                    bytes_data = uploaded_file.getvalue()
                    base64_str = base64.b64encode(bytes_data).decode('utf-8')
                    image_data = f"data:image/png;base64,{base64_str}"
                    st.info("⚠️ Image attached! (Note: Backend update required to post images)")

                new_post = {
                    "text": text_input, 
                    "schedule_time": dt_utc.isoformat(),
                    "image_data": image_data # Storing image in JSON
                }
                
                posts.append(new_post)
                save_to_github(posts, sha)
                
                st.session_state.tweet_content = "" 
                st.success(f"Scheduled for {hour_val}:{min_val:02d} {ampm} PKT")
                st.rerun()

    st.divider()
    st.subheader(f"Queue ({len(posts)})")
    if posts:
        posts.sort(key=lambda x: x['schedule_time'])
        for i, p in enumerate(posts):
            dt_utc = datetime.fromisoformat(p['schedule_time'])
            dt_pkt = dt_utc.astimezone(pkt_zone)
            with st.expander(f"{dt_pkt.strftime('%Y-%m-%d %I:%M %p')} - {p['text'][:30]}..."):
                st.text(p['text'])
                # Show image preview if exists
                if p.get("image_data"):
                    st.image(p["image_data"], width=200, caption="Attached Image")
                
                if st.button("Delete", key=f"d_{i}"):
                    posts.pop(i)
                    save_to_github(posts, sha)
                    st.rerun()

# --- PAGE 2: LEAD GEN (VIRAL) ---
elif selection == "Lead Gen (Viral)":
    st.title("⚡ Viral Lead Gen")
    st.caption("Scrapes Reddit for pain points -> Generates Viral Tweets under 280 chars.")
    
    if st.button("🎲 Fetch Reddit & Generate Posts"):
        with st.spinner("Analyzing Viral Trends..."):
            reddit_threads = fetch_reddit_viral()
            if reddit_threads:
                suggestions = generate_10_lead_posts(reddit_threads)
                st.session_state.lead_gen_suggestions = suggestions
            else:
                st.error("Reddit RSS busy. Try again.")

    if st.session_state.lead_gen_suggestions:
        st.markdown("### 🎯 Pick a Winner")
        for idx, post in enumerate(st.session_state.lead_gen_suggestions):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(post['tweet'])
                    st.caption(f"Topic: {post.get('topic')} | Len: {len(post['tweet'])}")
                with c2:
                    if st.button("🚀 Use This", key=f"use_{idx}"):
                        switch_to_scheduler(post['tweet'])

# --- PAGE 3: TECH NEWS (REDDIT) ---
elif selection == "Tech News (Reddit)":
    st.title("📰 Top Tech News")
    st.caption("Fresh from r/technology & r/ArtificialIntelligence")
    
    if st.button("🔄 Refresh News"):
        with st.spinner("Fetching RSS..."):
            st.session_state.news_cache = fetch_reddit_tech_news()
    
    if st.session_state.news_cache:
        for article in st.session_state.news_cache:
            with st.container(border=True):
                st.markdown(f"**{article['title']}**")
                if st.button("✨ Write Tweet", key=article['link']):
                    with st.spinner("Drafting..."):
                        tweet = generate_news_tweet(article['title'], article['link'])
                        switch_to_scheduler(tweet)

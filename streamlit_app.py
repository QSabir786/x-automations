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
except Exception:
    st.error("❌ Secrets missing! Check Streamlit Settings.")
    st.stop()

# Initialize Session State
if "tweet_content" not in st.session_state: st.session_state.tweet_content = ""
if "page_selection" not in st.session_state: st.session_state.page_selection = "Post Scheduler"
if "lead_gen_suggestions" not in st.session_state: st.session_state.lead_gen_suggestions = []
if "news_suggestions" not in st.session_state: st.session_state.news_suggestions = []
if "remix_suggestions" not in st.session_state: st.session_state.remix_suggestions = []

# --- HELPER FUNCTIONS ---

def get_gemini_model(temp=0.7):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
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

# --- FETCHERS ---

def fetch_reddit_viral_lead_gen():
    rss_url = "https://www.reddit.com/r/SaaS+Entrepreneur+Marketing+Agency/top.rss?t=week&limit=50"
    try:
        feed = feedparser.parse(rss_url)
        entries = feed.entries
        random.shuffle(entries)
        return [f"Title: {e.title}\nLink: {e.link}" for e in entries[:15]]
    except: return []

def fetch_reddit_tech_news():
    rss_url = "https://www.reddit.com/r/LocalLLaMA+LangChain+OpenAI+ArtificialIntelligence/top.rss?t=day&limit=50"
    try:
        feed = feedparser.parse(rss_url)
        entries = feed.entries
        clean_entries = [e for e in entries if "help" not in e.title.lower() and "?" not in e.title]
        random.shuffle(clean_entries)
        return [f"Headline: {e.title}\nLink: {e.link}" for e in clean_entries[:15]]
    except: return []

# --- AI GENERATORS ---

def generate_remix_batch(raw_text):
    """Takes raw feed text and generates 10 Viral Tweets."""
    llm = get_gemini_model(temp=0.8)
    template = """
    You are a Viral Social Media Architect.
    I have pasted raw text from my X/Twitter feed below.
    
    TASK: 
    Extract the best stories, news, or insights from this raw text and rewrite them into 10 unique tweets.
    
    CATEGORIES (Mix these):
    - 4x Value/Educational (Teach something)
    - 3x News/Hype (Breaking news)
    - 3x Entertainment/Motivation (Fun or inspiring)
    
    STRICT RULES:
    1. LENGTH: Must be under 280 chars.
    2. HOOKS: Start with a strong hook.
    3. HASHTAGS: End with 2 relevant hashtags.
    
    RAW INPUT TEXT:
    {raw_text}
    
    OUTPUT JSON:
    [{{ "category": "Value", "tweet": "...", "source": "Extracted Topic" }}]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"raw_text": raw_text})

def generate_lead_posts_batch(reddit_data):
    llm = get_gemini_model(temp=0.8)
    template = """
    You are a Viral B2B Ghostwriter. Read these Reddit threads and create 10 DISTINCT "Lead Gen" tweets.
    STRICT RULES:
    1. LENGTH: MUST be under 280 characters.
    2. STYLE: Hook -> Pain Point -> Solution -> CTA.
    INPUT: {reddit_data}
    OUTPUT JSON: [{{ "topic": "...", "tweet": "...", "source": "..." }}]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"reddit_data": "\n\n".join(reddit_data)})

def generate_news_posts_batch(reddit_data):
    llm = get_gemini_model(temp=0.6)
    template = """
    You are a Tech Influencer. Read these Reddit headlines and create 10 News Tweets.
    STRICT RULES:
    1. LENGTH: MUST be under 280 characters.
    2. STYLE: "Vibe coding", exciting, informative.
    INPUT: {reddit_data}
    OUTPUT JSON: [{{ "topic": "AI News", "tweet": "...", "source": "..." }}]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"reddit_data": "\n\n".join(reddit_data)})

# --- NAVIGATION ---
st.sidebar.title("🚀 Agency Panel")
selection = st.sidebar.radio("Go to:", ["Post Scheduler", "Feed Remix (Copy/Paste)", "Lead Gen (Viral)", "Tech News (AI/Code)"], key="nav_radio")

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
        # Added character counter here!
        text_input = st.text_area("Tweet Content", value=st.session_state.tweet_content, height=150, max_chars=280)
        
        # IMAGE UPLOADER
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
                
                image_data = None
                if uploaded_file:
                    bytes_data = uploaded_file.getvalue()
                    base64_str = base64.b64encode(bytes_data).decode('utf-8')
                    image_data = f"data:image/png;base64,{base64_str}"
                    st.info("Image saved!")

                posts.append({
                    "text": text_input, 
                    "schedule_time": dt_utc.isoformat(),
                    "image_data": image_data
                })
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
            with st.expander(f"{dt_pkt.strftime('%I:%M %p')} - {p['text'][:30]}..."):
                st.text(p['text'])
                if p.get("image_data"): st.image(p["image_data"], width=150)
                if st.button("Delete", key=f"d_{i}"):
                    posts.pop(i)
                    save_to_github(posts, sha)
                    st.rerun()

# --- PAGE 2: FEED REMIX (NEW!) ---
elif selection == "Feed Remix (Copy/Paste)":
    st.title("♻️ Feed Remix Engine")
    st.caption("Paste messy text (from X feed, blogs, chats). Get 10 viral tweets.")
    
    raw_text = st.text_area("Paste Raw Text Here:", height=200, placeholder="Paste your X timeline text here...")
    
    # Word/Char Counter
    if raw_text:
        st.caption(f"Stats: {len(raw_text)} chars | {len(raw_text.split())} words")
    
    if st.button("✨ Generate 10 Viral Remixes"):
        if not raw_text or len(raw_text) < 50:
            st.warning("Paste more text first!")
        else:
            with st.spinner("Finding the best stories..."):
                st.session_state.remix_suggestions = generate_remix_batch(raw_text)

    if st.session_state.remix_suggestions:
        st.markdown("### 💎 Your Remixed Tweets")
        for idx, post in enumerate(st.session_state.remix_suggestions):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(post['tweet'])
                    st.caption(f"Category: {post.get('category')} | Source: {post.get('source')}")
                with c2:
                    if st.button("🚀 Use This", key=f"remix_{idx}"):
                        switch_to_scheduler(post['tweet'])

# --- PAGE 3: LEAD GEN (VIRAL) ---
elif selection == "Lead Gen (Viral)":
    st.title("⚡ Viral Lead Gen")
    
    if st.button("🎲 Fetch & Generate 10 Posts"):
        with st.spinner("Analyzing Viral Trends..."):
            threads = fetch_reddit_viral_lead_gen()
            if threads:
                st.session_state.lead_gen_suggestions = generate_lead_posts_batch(threads)
            else:
                st.error("Reddit RSS busy.")

    if st.session_state.lead_gen_suggestions:
        for idx, post in enumerate(st.session_state.lead_gen_suggestions):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(post['tweet'])
                    st.caption(f"Topic: {post.get('topic')}")
                with c2:
                    if st.button("🚀 Use This", key=f"lg_{idx}"):
                        switch_to_scheduler(post['tweet'])

# --- PAGE 4: TECH NEWS (AI/CODE) ---
elif selection == "Tech News (AI/Code)":
    st.title("🤖 AI & Code News")
    
    if st.button("🔄 Fetch & Generate 10 News Tweets"):
        with st.spinner("Reading AI News..."):
            threads = fetch_reddit_tech_news()
            if threads:
                st.session_state.news_suggestions = generate_news_posts_batch(threads)
            else:
                st.error("Reddit RSS busy.")

    if st.session_state.news_suggestions:
        for idx, post in enumerate(st.session_state.news_suggestions):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(post['tweet'])
                    st.caption(f"Source: {post.get('source')}")
                with c2:
                    if st.button("🚀 Use This", key=f"news_{idx}"):
                        switch_to_scheduler(post['tweet'])

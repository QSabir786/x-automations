import streamlit as st
import requests
import base64
import json
import pytz
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
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("❌ Secrets missing! Check Streamlit Settings.")
    st.stop()

# Initialize Session State
if "tweet_content" not in st.session_state: st.session_state.tweet_content = ""
if "page_selection" not in st.session_state: st.session_state.page_selection = "Post Scheduler"
if "lead_gen_suggestions" not in st.session_state: st.session_state.lead_gen_suggestions = []

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

# --- REDDIT SCRAPER FUNCTIONS ---

def fetch_reddit_viral():
    """Scrapes top viral posts from AI subreddits."""
    # We hunt in these specific subreddits for "Pain Points" and "Hype"
    subreddits = "OpenAI+ArtificialIntelligence+SaaS+LocalLLaMA+LangChain"
    url = f"https://www.reddit.com/r/{subreddits}/top.json?t=week&limit=20"
    
    # User-Agent is CRITICAL to avoid being blocked
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        posts = []
        for child in data['data']['children']:
            post = child['data']
            # Only keep text-heavy posts or good discussions
            if not post.get('stickied') and len(post.get('title', '')) > 20:
                posts.append(f"Title: {post['title']}\nDiscussion: {post.get('selftext', '')[:500]}...\nLink: https://reddit.com{post['permalink']}")
        return posts
    except Exception as e:
        st.error(f"Reddit Error: {e}")
        return []

def generate_10_lead_posts(reddit_data):
    """Uses Gemini to turn Reddit threads into 10 B2B Lead Gen posts."""
    llm = get_gemini_model(temp=0.8)
    
    # We pass the raw Reddit text and ask for a JSON list of 10 tweets
    template = """
    You are an elite B2B Social Media Ghostwriter.
    I will give you a list of viral Reddit discussions about AI, SaaS, and Tech.
    
    TASK:
    Analyze the "Pain Points" or "Viral News" in these Reddit threads.
    Create 10 DISTINCT "Lead Gen" tweets based on them.
    
    STYLE RULES:
    - Format: Hook -> Problem -> Solution -> Call to Action.
    - Tone: "No-BS", Professional, Authority.
    - NO EMOJIS (Keep it raw).
    - Max 280 chars per tweet.
    - The Call to Action must be a question or "Reply 'AI' for help".
    
    INPUT DATA (Reddit Threads):
    {reddit_data}
    
    OUTPUT FORMAT (JSON ONLY):
    [
      {{"topic": "AI Agents", "tweet": "Your tweet here...", "source": "Reddit Thread Title"}},
      {{"topic": "SaaS", "tweet": "Your tweet here...", "source": "Reddit Thread Title"}}
    ]
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    
    # Join Reddit posts into one big string for analysis
    context = "\n\n".join(reddit_data[:15]) 
    return chain.invoke({"reddit_data": context})

def generate_news_tweet(title, url):
    """Generates a professional tech news update."""
    llm = get_gemini_model(temp=0.4)
    template = """
    You are a Senior Tech Analyst. Write a professional commentary on this news story.
    Headline: {title}
    Link: {url}
    Rules:
    - Tone: Insightful, Serious, Industry-focused.
    - NO EMOJIS.
    - Don't just summarize; add a "Why this matters" angle.
    - Max 250 characters.
    - Include 2 tags like #AI #Tech.
    """
    prompt = ChatPromptTemplate.from_template(template)
    return prompt | llm | (lambda x: x.invoke({"title": title, "url": url}).content)

def fetch_tech_news():
    query = '(OpenAI OR "Gemini 1.5" OR "Claude 3" OR "Llama 3" OR Nvidia OR DeepMind) AND (launch OR release OR benchmark OR "new model")'
    url = f"https://newsapi.org/v2/everything?q={query}&domains=techcrunch.com,wired.com,theverge.com,venturebeat.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    try:
        resp = requests.get(url)
        return resp.json().get("articles", [])[:6]
    except:
        return []

# --- NAVIGATION ---
st.sidebar.title("🚀 Agency Panel")
selection = st.sidebar.radio("Go to:", ["Post Scheduler", "Lead Gen (Reddit Scraper)", "AI News Hunter"], key="nav_radio")

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
                
                posts.append({"text": text_input, "schedule_time": dt_utc.isoformat()})
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
                if st.button("Delete", key=f"d_{i}"):
                    posts.pop(i)
                    save_to_github(posts, sha)
                    st.rerun()

# --- PAGE 2: LEAD GEN (REDDIT SCRAPER) ---
elif selection == "Lead Gen (Reddit Scraper)":
    st.title("⚡ Viral Lead Gen Generator")
    st.caption("Scrapes r/OpenAI, r/SaaS, r/LocalLLaMA for viral pain points.")
    
    if st.button("🎲 Fetch Viral Reddit Threads & Generate 10 Posts"):
        with st.spinner("Scraping Reddit... Reading Threads... Generating Hooks..."):
            # 1. Get Real Data
            reddit_threads = fetch_reddit_viral()
            if reddit_threads:
                # 2. AI Magic
                suggestions = generate_10_lead_posts(reddit_threads)
                st.session_state.lead_gen_suggestions = suggestions
            else:
                st.error("Failed to fetch Reddit data. Try again in 1 minute.")

    # DISPLAY THE 10 SUGGESTIONS
    if st.session_state.lead_gen_suggestions:
        st.markdown("### 🎯 Choose a Post to Schedule")
        
        for idx, post in enumerate(st.session_state.lead_gen_suggestions):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**Topic:** {post.get('topic', 'General')}")
                    st.text_area("Draft", value=post['tweet'], height=100, key=f"draft_{idx}", disabled=True)
                    st.caption(f"Inspired by Reddit: *{post.get('source', 'Unknown')}*")
                with c2:
                    st.write("") # Spacer
                    st.write("") # Spacer
                    if st.button("🚀 Use This", key=f"use_{idx}"):
                        switch_to_scheduler(post['tweet'])

# --- PAGE 3: AI NEWS HUNTER ---
elif selection == "AI News Hunter":
    st.title("🕵️ Tech News Hunter")
    
    if st.button("🔎 Fetch Latest News"):
        with st.spinner("Hunting for alpha..."):
            st.session_state.news_cache = fetch_tech_news()
    
    if "news_cache" in st.session_state:
        for article in st.session_state.news_cache:
            with st.container(border=True):
                st.markdown(f"**{article['title']}**")
                st.caption(f"{article['source']['name']} • {article['publishedAt'][:10]}")
                if st.button("✨ Write Professional Tweet", key=article['url']):
                    with st.spinner("Analyzing..."):
                        tweet = generate_news_tweet(article['title'], article['url'])
                        switch_to_scheduler(tweet)

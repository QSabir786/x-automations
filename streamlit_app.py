import streamlit as st
import requests
import base64
import json
import pytz
import random
from datetime import datetime, time, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

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

# --- AI FUNCTIONS ---

def generate_lead_gen_post():
    """Generates a high-converting B2B post based on user's examples."""
    llm = get_gemini_model(temp=0.9) # Higher creativity for variety
    
    template = """
    You are an elite B2B Consultant and Copywriter.
    Write a "No-BS", high-converting LinkedIn/X post targeting business owners who need AI automation and Websites.
    
    STYLE GUIDE:
    - Direct, punchy, slightly controversial.
    - Start with a "Hook" that attacks a pain point (e.g., wasted time, bad websites, profit leaks).
    - Agitate the problem.
    - Offer a clear solution (AI, Automation, Strategy).
    - End with a specific Call to Action (Question or "Reply with X").
    - NO EMOJIS (Keep it raw and professional).
    - Max 280 chars (or slightly more for threading, but keep it tight).
    
    TOPICS (Pick ONE):
    1. Websites that don't convert are expensive brochures.
    2. Employees doing $5/hr tasks (Data entry vs AI).
    3. Chatbots that just say "Hello" vs Chatbots that sell.
    4. The silent revenue killer (Manual onboarding).
    5. Starting AI with problems, not technology.
    
    OUTPUT: Just the tweet text.
    """
    prompt = ChatPromptTemplate.from_template(template)
    return prompt | llm | (lambda x: x.content)

def generate_news_tweet(title, url):
    """Generates a professional tech news update."""
    llm = get_gemini_model(temp=0.4) # Lower temp for accuracy
    
    template = """
    You are a Senior Tech Analyst.
    Write a professional commentary on this news story.
    
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

# Manual navigation handling to support "Teleporting"
selection = st.sidebar.radio("Go to:", ["Post Scheduler", "AI News Hunter", "Lead Gen Posts"], key="nav_radio")

# Force update if session state changed (Teleport logic)
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
        # This box gets auto-filled by the other pages
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
                
                # Clear content after posting
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

# --- PAGE 2: AI NEWS HUNTER ---
elif selection == "AI News Hunter":
    st.title("🕵️ Tech News Hunter")
    st.caption("Finds real updates from OpenAI, Anthropic, Nvidia, etc.")
    
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

# --- PAGE 3: LEAD GEN GENERATOR ---
elif selection == "Lead Gen Posts":
    st.title("⚡ Client Magnet Generator")
    st.caption("Generates 'No-BS' posts to attract business owners.")
    
    if st.button("🎲 Generate New Idea"):
        with st.spinner("Brainstorming pain points..."):
            post_idea = generate_lead_gen_post().invoke({})
            st.session_state.lead_gen_cache = post_idea
            
    if "lead_gen_cache" in st.session_state:
        st.markdown("### 💡 Draft Post")
        st.info(st.session_state.lead_gen_cache)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Regenerate"):
                with st.spinner("Thinking of another angle..."):
                    post_idea = generate_lead_gen_post().invoke({})
                    st.session_state.lead_gen_cache = post_idea
                    st.rerun()
        with col2:
            if st.button("🚀 Use This Post"):
                switch_to_scheduler(st.session_state.lead_gen_cache)

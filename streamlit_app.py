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
st.set_page_config(page_title="X Command Center", page_icon="🇵🇰", layout="wide")
st.title("🇵🇰 X Command Center (Pro Mode)")

# --- AUTHENTICATION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.write("🔒 Login Required")
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

if "tweet_content" not in st.session_state: st.session_state.tweet_content = ""
if "image_url" not in st.session_state: st.session_state.image_url = ""

# --- FUNCTIONS ---
def get_ai_content(title, url):
    """Uses Gemini to write a PRO tweet AND a MODERN image prompt."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.5 # Lower temperature = less random, more professional
        )
        
        # UPDATED PROMPT FOR PROFESSIONALISM
        template = """
        You are a senior tech analyst on X (Twitter).
        
        TASK 1: Write a professional, insightful tweet.
        - Headline: {title}
        - Link: {url}
        - Style: Concise, analytical, professional. Like a tech journalist.
        - NO EMOJIS. NO asterisks (**).
        - Max length: 250 chars.
        - Include 2 professional hashtags (e.g., #TechNews, #AI).
        
        TASK 2: Write a prompt for a modern, abstract tech image.
        - Style: Futuristic, clean, high-tech, modern design.
        - Colors: Deep blues, purples, electric cyan, dark mode aesthetic.
        - Content: Abstract data visualization, circuit patterns, geometric shapes.
        - CRITICAL: DO NOT include any text, logos, or letters in the image description.
        
        OUTPUT FORMAT:
        Tweet: [Your tweet here]
        Image Prompt: [Your image prompt here]
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm
        result = chain.invoke({"title": title, "url": url}).content
        
        tweet_text = result.split("Image Prompt:")[0].replace("Tweet:", "").strip()
        img_prompt = result.split("Image Prompt:")[1].strip()
        return tweet_text, img_prompt
        
    except Exception as e:
        return f"Error: {str(e)}", "abstract tech blue purple"

def fetch_tech_news():
    """Hunts for SPECIFIC high-tech news."""
    query = '(OpenAI OR Gemini OR "Claude 3" OR "Llama 3" OR "Nvidia" OR Waymo) AND (launch OR release OR update OR growth OR benchmark)'
    url = f"https://newsapi.org/v2/everything?q={query}&domains=techcrunch.com,wired.com,theverge.com,reuters.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    try:
        resp = requests.get(url)
        data = resp.json()
        return data.get("articles", [])[:6]
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
col_scheduler, col_news = st.columns([1, 1])

with col_news:
    st.subheader("🕵️ Pro Tech News")
    if st.button("🔎 Fetch News"):
        news_items = fetch_tech_news()
        st.session_state.news_cache = news_items
    
    if "news_cache" in st.session_state:
        for article in st.session_state.news_cache:
            with st.container(border=True):
                st.markdown(f"**{article['title']}**")
                st.caption(f"{article['source']['name']} • {article['publishedAt'][:10]}")
                if st.button("✨ Create Pro Post", key=article['url']):
                    with st.spinner("Analyzing & Designing..."):
                        tweet, img_prompt = get_ai_content(article['title'], article['url'])
                        clean_prompt = img_prompt.replace(" ", "%20")
                        # Add 'modern' tag and increase quality
                        st.session_state.image_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1200&height=675&nologo=true&model=flux"
                        st.session_state.tweet_content = tweet
                        st.rerun()

with col_scheduler:
    st.subheader("📅 Scheduler")
    posts, sha = get_github_data()
    pkt_zone = pytz.timezone('Asia/Karachi')
    utc_zone = pytz.utc

    with st.form("schedule_form", clear_on_submit=True):
        text_input = st.text_area("Tweet Content", value=st.session_state.tweet_content, height=150, max_chars=280)
        if st.session_state.image_url:
            st.image(st.session_state.image_url, caption="AI Generated Visual (Save & Attach Manually)", width=400)

        st.write("**Schedule Time (PKT)**")
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        date_val = c1.date_input("Date")
        hour_val = c2.selectbox("Hour", range(1, 13))
        min_val = c3.selectbox("Minute", range(0, 60))
        ampm = c4.selectbox("AM/PM", ["AM", "PM"])
        
        if st.form_submit_button("🚀 Schedule Post"):
            if not text_input: st.warning("Write something first!")
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
                st.session_state.image_url = ""
                st.success("Scheduled!")
                st.rerun()

    st.divider()
    st.write(f"**Queue ({len(posts)}):**")
    if posts:
        posts.sort(key=lambda x: x['schedule_time'])
        for i, p in enumerate(posts):
            dt_utc = datetime.fromisoformat(p['schedule_time'])
            dt_pkt = dt_utc.astimezone(pkt_zone)
            with st.expander(f"{dt_pkt.strftime('%I:%M %p')} - {p['text'][:30]}..."):
                st.text(p['text'])
                if st.button("Delete", key=f"d_{i}"):
                    posts.pop(i)
                    save_to_github(posts, sha)
                    st.rerun()

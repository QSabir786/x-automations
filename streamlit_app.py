import streamlit as st
import requests
import base64
import json
import pytz
import feedparser
import random
import uuid # <--- NEW: To track threads
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
if "thread_drafts" not in st.session_state: st.session_state.thread_drafts = []

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
def process_thread_text(raw_text):
    llm = get_gemini_model(temp=0.3)
    template = """
    You are a Twitter Thread Editor.
    TASK: Split text into tweets. If >280 chars, rewrite to shorter.
    RAW TEXT: {raw_text}
    OUTPUT JSON: ["Tweet 1", "Tweet 2"]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"raw_text": raw_text})

def generate_remix_batch(raw_text):
    llm = get_gemini_model(temp=0.8)
    template = """
    You are a Viral Social Media Architect.
    Extract stories from this raw text and rewrite them into 10 unique tweets.
    STRICT RULES:
    1. LENGTH: Must be under 280 chars.
    2. HOOKS: Start with a strong hook.
    RAW INPUT: {raw_text}
    OUTPUT JSON: [{{ "category": "Value", "tweet": "...", "source": "Extracted Topic" }}]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"raw_text": raw_text})

def generate_lead_posts_batch(reddit_data):
    llm = get_gemini_model(temp=0.8)
    template = """
    You are a Viral B2B Ghostwriter. Create 10 DISTINCT "Lead Gen" tweets.
    STRICT RULES:
    1. LENGTH: MUST be under 280 chars.
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
    You are a Tech Influencer. Create 10 News Tweets.
    STRICT RULES:
    1. LENGTH: MUST be under 280 chars.
    INPUT: {reddit_data}
    OUTPUT JSON: [{{ "topic": "AI News", "tweet": "...", "source": "..." }}]
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()
    return chain.invoke({"reddit_data": "\n\n".join(reddit_data)})

# --- NAVIGATION ---
st.sidebar.title("🚀 Agency Panel")
selection = st.sidebar.radio("Go to:", ["Post Scheduler", "Thread Creator (New)", "Feed Remix", "Lead Gen", "Tech News"], key="nav_radio")

if st.session_state.page_selection != selection:
    st.session_state.page_selection = selection
    st.rerun()

# --- PAGE 1: POST SCHEDULER ---
if selection == "Post Scheduler":
    st.title("📅 Post Scheduler")
    posts, sha = get_github_data()
    pkt_zone = pytz.timezone('Asia/Karachi')
    utc_zone = pytz.utc

    # --- 1. NEW TWEET FORM ---
    with st.form("schedule_form", clear_on_submit=True):
        text_input = st.text_area("Tweet Content", value=st.session_state.tweet_content, height=150, max_chars=280)
        st.caption(f"Chars: {len(text_input)}/280")
        
        uploaded_file = st.file_uploader("📷 Attach Image (Optional)", type=["png", "jpg", "jpeg"])
        
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
                
                image_data = None
                if uploaded_file:
                    bytes_data = uploaded_file.getvalue()
                    b64 = base64.b64encode(bytes_data).decode('utf-8')
                    image_data = f"data:image/png;base64,{b64}"

                # No thread_id for single posts
                posts.append({"text": text_input, "schedule_time": dt_utc.isoformat(), "image_data": image_data, "thread_id": None})
                save_to_github(posts, sha)
                st.session_state.tweet_content = "" 
                st.success("Scheduled!")
                st.rerun()

    st.divider()
    
    # --- 2. SMART QUEUE (GROUPED THREADS) ---
    st.subheader(f"Queue ({len(posts)} Tweets)")
    
    if posts:
        # Sort by time
        posts.sort(key=lambda x: x['schedule_time'])
        
        # Group posts by thread_id
        grouped_posts = []
        processed_indices = set()
        
        for i, p in enumerate(posts):
            if i in processed_indices: continue
            
            t_id = p.get("thread_id")
            
            # If it has a thread_id, find all siblings
            if t_id:
                thread_siblings = []
                for j, sibling in enumerate(posts):
                    if sibling.get("thread_id") == t_id:
                        thread_siblings.append((j, sibling)) # Store index and post
                        processed_indices.add(j)
                grouped_posts.append({"type": "thread", "items": thread_siblings})
            else:
                # Normal single post
                grouped_posts.append({"type": "single", "items": [(i, p)]})
                processed_indices.add(i)

        # RENDER THE QUEUE
        for group in grouped_posts:
            # --- RENDER SINGLE POST ---
            if group["type"] == "single":
                idx, p = group["items"][0]
                dt_utc = datetime.fromisoformat(p['schedule_time'])
                dt_pkt = dt_utc.astimezone(pkt_zone)
                
                with st.expander(f"📝 {dt_pkt.strftime('%I:%M %p')} - {p['text'][:30]}..."):
                    st.text(p['text'])
                    if p.get("image_data"): st.image(p["image_data"], width=150)
                    if st.button("Delete", key=f"del_{idx}"):
                        posts.pop(idx)
                        save_to_github(posts, sha)
                        st.rerun()
            
            # --- RENDER THREAD ---
            elif group["type"] == "thread":
                first_idx, first_p = group["items"][0]
                dt_utc = datetime.fromisoformat(first_p['schedule_time'])
                dt_pkt = dt_utc.astimezone(pkt_zone)
                count = len(group["items"])
                
                with st.expander(f"🧵 THREAD ({count} Tweets) - Starts {dt_pkt.strftime('%I:%M %p')}"):
                    st.info("These tweets are linked and scheduled 1 minute apart.")
                    
                    for sub_idx, sub_p in group["items"]:
                        st.markdown(f"**Tweet:**")
                        st.text(sub_p['text'])
                        if sub_p.get("image_data"): st.image(sub_p["image_data"], width=100)
                        st.divider()
                    
                    if st.button(f"🗑️ Delete Entire Thread", key=f"del_thread_{first_idx}"):
                        # Remove all items in this thread (reverse order to avoid index shift issues)
                        indices_to_remove = sorted([x[0] for x in group["items"]], reverse=True)
                        for rm_idx in indices_to_remove:
                            posts.pop(rm_idx)
                        save_to_github(posts, sha)
                        st.rerun()

# --- PAGE 2: THREAD CREATOR ---
elif selection == "Thread Creator (New)":
    st.title("🧵 Thread Master")
    raw_thread = st.text_area("Paste Full Thread:", height=200)

    if st.button("✂️ Process"):
        if raw_thread:
            with st.spinner("Processing..."):
                st.session_state.thread_drafts = process_thread_text(raw_thread)
    
    if st.session_state.thread_drafts:
        st.divider()
        with st.form("thread_form"):
            updated_texts = []
            updated_images = []
            for idx, draft in enumerate(st.session_state.thread_drafts):
                st.markdown(f"**Tweet {idx+1}**")
                txt = st.text_area(f"T{idx+1}", value=draft, height=100, key=f"t_{idx}")
                img = st.file_uploader(f"Img {idx+1}", type=['png', 'jpg'], key=f"i_{idx}")
                updated_texts.append(txt)
                updated_images.append(img)
                st.caption(f"Chars: {len(txt)}/280")
                st.write("---")

            st.write("### 🕒 Schedule Start")
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            date_val = c1.date_input("Date")
            hour_val = c2.selectbox("Hour", range(1, 13))
            min_val = c3.selectbox("Minute", range(0, 60))
            ampm = c4.selectbox("AM/PM", ["AM", "PM"])

            if st.form_submit_button("🚀 Schedule Thread"):
                h24 = hour_val
                if ampm == "PM" and hour_val != 12: h24 += 12
                if ampm == "AM" and hour_val == 12: h24 = 0
                pkt_zone = pytz.timezone('Asia/Karachi')
                utc_zone = pytz.utc
                
                dt_naive = datetime.combine(date_val, time(h24, min_val))
                start_dt_pkt = pkt_zone.localize(dt_naive)
                
                posts, sha = get_github_data()
                
                # GENERATE A UNIQUE THREAD ID
                new_thread_id = str(uuid.uuid4())
                
                for i, (txt, img_file) in enumerate(zip(updated_texts, updated_images)):
                    post_time = start_dt_pkt + timedelta(minutes=i)
                    post_time_utc = post_time.astimezone(utc_zone)
                    
                    image_data = None
                    if img_file:
                        b64 = base64.b64encode(img_file.getvalue()).decode('utf-8')
                        image_data = f"data:image/png;base64,{b64}"
                    
                    posts.append({
                        "text": txt,
                        "schedule_time": post_time_utc.isoformat(),
                        "image_data": image_data,
                        "thread_id": new_thread_id # <--- LINK THEM TOGETHER
                    })
                
                save_to_github(posts, sha)
                st.success("✅ Thread Scheduled!")
                st.session_state.thread_drafts = []
                st.rerun()

# --- OTHER PAGES (FEED REMIX / LEAD GEN / NEWS) ---
# (Keeping these simple and robust)
elif selection == "Feed Remix":
    st.title("♻️ Feed Remix")
    raw = st.text_area("Paste Feed Text:", height=150)
    if st.button("✨ Remix") and raw:
        st.session_state.remix_suggestions = generate_remix_batch(raw)
    if st.session_state.remix_suggestions:
        for idx, p in enumerate(st.session_state.remix_suggestions):
            with st.container(border=True):
                st.write(p['tweet'])
                if st.button("🚀 Use", key=f"rm_{idx}"): switch_to_scheduler(p['tweet'])

elif selection == "Lead Gen":
    st.title("⚡ Lead Gen")
    if st.button("🎲 Fetch"):
        th = fetch_reddit_viral_lead_gen()
        if th: st.session_state.lead_gen_suggestions = generate_lead_posts_batch(th)
    if st.session_state.lead_gen_suggestions:
        for idx, p in enumerate(st.session_state.lead_gen_suggestions):
            with st.container(border=True):
                st.write(p['tweet'])
                if st.button("🚀 Use", key=f"lg_{idx}"): switch_to_scheduler(p['tweet'])

elif selection == "Tech News":
    st.title("🤖 AI News")
    if st.button("🔄 Fetch"):
        th = fetch_reddit_tech_news()
        if th: st.session_state.news_suggestions = generate_news_posts_batch(th)
    if st.session_state.news_suggestions:
        for idx, p in enumerate(st.session_state.news_suggestions):
            with st.container(border=True):
                st.write(p['tweet'])
                if st.button("🚀 Use", key=f"nw_{idx}"): switch_to_scheduler(p['tweet'])

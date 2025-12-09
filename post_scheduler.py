import requests
import base64
import json
import os
import tweepy
from datetime import datetime, timezone

# --- 1. LOCAL TESTING SETUP ---
# This tries to load .env. If it fails (like on GitHub), it just keeps going.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- 2. CONFIGURATION ---
# It will look for these in .env (Local) OR GitHub Secrets (Online)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
FILE_PATH = "scheduled_posts.json"

TWITTER_CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# --- 3. HELPER FUNCTIONS ---
def get_posts_from_github():
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"⚠️ Could not find or read {FILE_PATH}. (Status: {response.status_code})")
        return [], None
        
    data = response.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    if not content.strip():
        return [], data["sha"]
    return json.loads(content), data["sha"]

def update_github_file(new_posts, sha):
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    encoded_content = base64.b64encode(json.dumps(new_posts, indent=2).encode("utf-8")).decode("utf-8")
    
    body = {
        "message": "Updated posts via Scheduler",
        "content": encoded_content,
        "sha": sha
    }
    
    response = requests.put(url, headers=HEADERS, json=body)
    if response.status_code in [200, 201]:
        print("✅ GitHub file updated successfully.")
    else:
        print(f"❌ Failed to update GitHub. Status: {response.status_code}")

# --- 4. MAIN LOGIC ---
def main():
    print(f"--- Running Scheduler at {datetime.now(timezone.utc)} UTC ---")
    
    # Check if keys exist
    if not GITHUB_TOKEN or not TWITTER_CONSUMER_KEY:
        print("❌ Error: Missing API Keys. Check your .env file or GitHub Secrets.")
        return

    # 1. Get posts
    posts, sha = get_posts_from_github()
    if not posts:
        print("No scheduled posts found.")
        return

    # 2. Setup Twitter Client
    client = tweepy.Client(
        consumer_key=TWITTER_CONSUMER_KEY,
        consumer_secret=TWITTER_CONSUMER_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )

    now = datetime.now(timezone.utc)
    remaining_posts = []
    posts_made = 0

    # 3. Check every post
    for post in posts:
        try:
            scheduled_time = datetime.fromisoformat(post['schedule_time'])
            
            # If time has passed, POST IT
            if scheduled_time <= now:
                print(f"🚀 Posting: {post['text'][:30]}...")
                client.create_tweet(text=post['text'])
                print("   -> Success!")
                posts_made += 1
                # We do NOT add it to remaining_posts, so it gets deleted
            else:
                remaining_posts.append(post)
                
        except Exception as e:
            print(f"❌ Error processing post: {e}")
            remaining_posts.append(post) # Keep it if it failed to be safe

    # 4. Save changes if we posted something
    if posts_made > 0:
        update_github_file(remaining_posts, sha)
    else:
        print("No posts were due right now.")

if __name__ == "__main__":
    main()
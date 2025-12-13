import requests
import base64
import json
import os
import tweepy
import time
import tempfile
from datetime import datetime, timezone

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
FILE_PATH = "scheduled_posts.json"

# KEYS
CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# --- GITHUB HELPER FUNCTIONS ---
def get_posts():
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200: return [], None
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content) if content.strip() else [], data["sha"]

def update_file(posts, sha):
    url = f"{BASE_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{FILE_PATH}"
    content = base64.b64encode(json.dumps(posts, indent=2).encode("utf-8")).decode("utf-8")
    body = {"message": "Updated queue via Scheduler", "content": content, "sha": sha}
    requests.put(url, headers=HEADERS, json=body)

# --- IMAGE HELPER FUNCTION ---
def upload_image(api, base64_string):
    """Decodes base64 string and uploads to Twitter. Returns Media ID."""
    try:
        if not base64_string: return None
        
        # Split header "data:image/png;base64," from the actual data
        if "," in base64_string:
            header, encoded = base64_string.split(",", 1)
        else:
            encoded = base64_string

        # Create a temporary file to save the image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_file.write(base64.b64decode(encoded))
            temp_filename = temp_file.name

        # Upload using v1.1 API (Required for Media)
        media = api.media_upload(filename=temp_filename)
        
        # Clean up temp file
        os.remove(temp_filename)
        
        return media.media_id
    except Exception as e:
        print(f"❌ Image Upload Error: {e}")
        return None

# --- MAIN LOGIC ---
def main():
    print("--- Checking Schedule ---")
    posts, sha = get_posts()
    if not posts: return

    # 1. SETUP TWITTER AUTH (Need BOTH Client for text and API for images)
    # V2 Client (For Posting)
    client = tweepy.Client(
        consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN, access_token_secret=ACCESS_SECRET
    )
    # V1.1 API (For Image Uploads - Tweepy requirement)
    auth = tweepy.OAuth1UserHandler(
        CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_SECRET
    )
    api = tweepy.API(auth)

    now = datetime.now(timezone.utc)
    processed_indices = set()
    
    # Sort by time so threads are ordered (1/, 2/, 3/)
    posts.sort(key=lambda x: x['schedule_time'])

    for i, post in enumerate(posts):
        if i in processed_indices: continue

        scheduled = datetime.fromisoformat(post['schedule_time'])
        
        # IF POST IS DUE
        if scheduled <= now:
            try:
                # CHECK: Is this part of a Thread?
                thread_id = post.get("thread_id")
                
                if thread_id:
                    print(f"🧵 Found Thread Chain: {thread_id}")
                    # Find all parts of this thread
                    thread_parts = [p for p in posts if p.get("thread_id") == thread_id]
                    
                    last_tweet_id = None
                    
                    # POST LOOP
                    for part in thread_parts:
                        print(f"   -> Posting Part: {part['text'][:20]}...")
                        
                        # A. Handle Image
                        media_ids = None
                        if part.get("image_data"):
                            print("      Creating Image...")
                            media_id = upload_image(api, part["image_data"])
                            if media_id: media_ids = [media_id]

                        # B. Post Tweet
                        if last_tweet_id:
                            # REPLY to previous
                            resp = client.create_tweet(
                                text=part['text'], 
                                media_ids=media_ids,
                                in_reply_to_tweet_id=last_tweet_id
                            )
                        else:
                            # FIRST TWEET
                            resp = client.create_tweet(
                                text=part['text'],
                                media_ids=media_ids
                            )
                        
                        # Save ID for next loop
                        last_tweet_id = resp.data['id']
                        
                        # Mark as done
                        processed_indices.add(posts.index(part))
                        time.sleep(2) # Safety pause
                        
                    print("✅ Thread Posted Successfully!")
                    
                else:
                    # SINGLE POST LOGIC
                    print(f"🚀 Posting Single: {post['text'][:20]}...")
                    
                    # Handle Image
                    media_ids = None
                    if post.get("image_data"):
                        print("      Creating Image...")
                        media_id = upload_image(api, post["image_data"])
                        if media_id: media_ids = [media_id]
                    
                    client.create_tweet(text=post['text'], media_ids=media_ids)
                    processed_indices.add(i)

            except Exception as e:
                print(f"❌ Error: {e}")
    
    # Update GitHub File (Delete processed posts)
    final_queue = [p for i, p in enumerate(posts) if i not in processed_indices]

    if len(final_queue) < len(posts):
        update_file(final_queue, sha)
        print("📝 Queue Cleaned.")
    else:
        print("💤 No posts due.")

if __name__ == "__main__":
    main()

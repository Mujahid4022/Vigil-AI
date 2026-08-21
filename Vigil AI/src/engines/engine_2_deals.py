"""
engine_2_deals.py - Universal Text‑only Engine
Uses per‑page settings: provider_priority, posts_per_run, post_interval
Dynamic model names fetched from config.json via get_model_name()
"""
import os
import time
import re
import json
import requests
from bs4 import BeautifulSoup
from config.config import get_api_key, get_model_name, get_page_token, FB_PAGE_ID_DEALS

# ----------------------------------------------------------------------
# Google Custom Search (optional)
# ----------------------------------------------------------------------
def google_search(query, api_key, search_engine_id):
    urls = []
    try:
        url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={search_engine_id}&q={query}&num=5"
        response = requests.get(url).json()
        if 'items' in response:
            for item in response['items']:
                urls.append(item['link'])
    except Exception as e:
        print(f"⚠️ Google Search Error: {e}")
    return urls

# ----------------------------------------------------------------------
# Scrape a URL and extract text + possible location info
# ----------------------------------------------------------------------
def scrape_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.find('title').get_text(strip=True) if soup.find('title') else ""
        desc = ""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content'):
            desc = meta['content']
        paragraphs = ' '.join([p.get_text() for p in soup.find_all('p')])[:2000]
        full_text = f"Title: {title}\nDescription: {desc}\nContent: {paragraphs}"
        return full_text
    except Exception as e:
        return f"Error: {e}"

# ----------------------------------------------------------------------
# Extract a city name from text (simple list of major Pakistan cities)
# ----------------------------------------------------------------------
def extract_city(text):
    cities = ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad",
              "Multan", "Hyderabad", "Peshawar", "Quetta", "Gujranwala"]
    for city in cities:
        if re.search(r'\b' + re.escape(city) + r'\b', text, re.IGNORECASE):
            return city
    return None

# ----------------------------------------------------------------------
# Main function – runs the Text Engine
# ----------------------------------------------------------------------
def run_engine_2():
    print(f"🤖 [Engine 2] Searching for latest deals...")

    page_id = FB_PAGE_ID_DEALS
    token = get_page_token(page_id)
    if not page_id or not token:
        print("❌ Deals page ID or token not set.")
        return

    CONFIG_FILE = "config.json"
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    page = None
    for p in config.get('pages', []):
        if p['id'] == page_id:
            page = p
            break
    if not page:
        print(f"❌ Page {page_id} not found in config.json")
        return

    google_api_key = config.get('api_keys', {}).get('google_api', '')
    google_engine_id = config.get('api_keys', {}).get('google_engine_id', '')
    search_query = page.get('google_query', 'Pakistan sale deals today')
    target_urls = page.get('urls', [])
    posts_per_run = page.get('posts_per_run', 2)
    post_interval = page.get('post_interval', 30)

    priority_list = page.get('provider_priority', 'gemini').split(',')
    priority_list = [p.strip() for p in priority_list if p.strip()]

    if google_api_key and google_engine_id:
        print(f"🔍 Googling: {search_query}")
        google_urls = google_search(search_query, google_api_key, google_engine_id)
        target_urls.extend(google_urls)
        print(f"📎 Found {len(google_urls)} search results.")

    target_urls = list(set(target_urls))
    if not target_urls:
        print("⚠️ No URLs to scrape. Skipping.")
        return

    max_urls = min(len(target_urls), posts_per_run)
    urls_to_process = target_urls[:max_urls]
    print(f"📋 Processing up to {len(urls_to_process)} URLs")

    all_posts = []

    for url in urls_to_process:
        print(f"📡 Scraping: {url}")
        scraped_text = scrape_page(url)
        if "Error" in scraped_text:
            continue

        city = extract_city(scraped_text)
        map_link = f"https://www.google.com/maps?q={city}" if city else None

        prompt = f"""You are a Facebook content creator. You found a page at this URL: {url}
Here is the scraped data from the site:
{scraped_text}

If there is no useful information (deal, news, scholarship, etc.), reply with exactly "NO CONTENT".
If there IS useful content, write a short, punchy, attractive Facebook post (in English) about it.
Structure it like this:
🎉 [Headline/Sale Name]
🔥 [Offer details]
🛍️ [Where/How to buy]
⏳ [Expiry date or "Hurry up!"]
🔗 {url}

If you find a physical store address (or city) in the text, add a line like:
📍 Available at: [Store Name, City] (or "📍 Available in [City]")
If the city is found, also add a Google Maps link: {map_link if map_link else ''}

Use emojis. Keep it brief and engaging. Do NOT use hashtags.
"""

        formatted_post = None
        # --- Dynamic Provider Priority Loop ---
        for provider in priority_list:
            api_key = get_api_key(provider)
            if not api_key:
                print(f"⏭️ No key for {provider}, skipping...")
                continue
            try:
                if provider == 'groq':
                    from groq import Groq
                    model = get_model_name('groq') or 'openai/gpt-oss-120b'
                    client = Groq(api_key=api_key)
                    print(f"🧠 Trying Groq ({model})...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    formatted_post = response.choices[0].message.content
                    print(f"✅ Successfully used {provider}")
                    break
                elif provider == 'openai':
                    from openai import OpenAI
                    model = get_model_name('openai') or 'gpt-4o'
                    client = OpenAI(api_key=api_key)
                    print(f"🧠 Trying OpenAI ({model})...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    formatted_post = response.choices[0].message.content
                    print(f"✅ Successfully used {provider}")
                    break
                elif provider == 'deepseek':
                    from openai import OpenAI
                    model = get_model_name('deepseek') or 'deepseek-chat'
                    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                    print(f"🧠 Trying DeepSeek ({model})...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    formatted_post = response.choices[0].message.content
                    print(f"✅ Successfully used {provider}")
                    break
                elif provider == 'anthropic':
                    from anthropic import Anthropic
                    model = get_model_name('anthropic') or 'claude-sonnet-5'
                    client = Anthropic(api_key=api_key)
                    print(f"🧠 Trying Anthropic ({model})...")
                    response = client.messages.create(
                        model=model,
                        max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    formatted_post = response.content[0].text
                    print(f"✅ Successfully used {provider}")
                    break
                elif provider == 'mistral':
                    from mistralai import Mistral
                    model = get_model_name('mistral') or 'mistral-medium-2508'
                    client = Mistral(api_key=api_key)
                    print(f"🧠 Trying Mistral ({model})...")
                    response = client.chat.complete(
                        model=model,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    formatted_post = response.choices[0].message.content
                    print(f"✅ Successfully used {provider}")
                    break
                else:  # Gemini
                    from google import genai
                    model = get_model_name('gemini') or 'models/gemini-3.5-flash'
                    client = genai.Client(api_key=api_key)
                    print(f"🧠 Trying Gemini ({model})...")
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    formatted_post = response.text.strip()
                    print(f"✅ Successfully used {provider}")
                    break
            except Exception as e:
                print(f"❌ {provider} failed: {e}, trying next...")
                formatted_post = None
                continue

        if formatted_post and formatted_post.strip() == "NO CONTENT":
            print(f"ℹ️ No relevant content found at {url} – skipping.")
            continue
        elif formatted_post:
            all_posts.append({'text': formatted_post, 'url': url})

    if not all_posts:
        print("❌ No valid posts to publish.")
        return

    print(f"📤 Posting {len(all_posts)} posts...")
    count = 0
    for deal in all_posts:
        fb_url = f"https://graph.facebook.com/v26.0/{page_id}/feed"
        payload = {'message': deal['text'], 'access_token': token}
        try:
            result = requests.post(fb_url, data=payload).json()
            if 'id' in result:
                print(f"✅ Posted Post {count+1}! ID: {result['id']}")
                count += 1
                time.sleep(post_interval)
            else:
                print(f"❌ FB Error: {result}")
        except Exception as e:
            print(f"❌ Connection Error: {e}")

    print(f"🔄 [Engine 2] Finished. Posted {count} posts.")
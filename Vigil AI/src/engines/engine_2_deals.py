"""
engine_2_deals.py - Universal Engine 2 (Load Balancer Worker 2)

This engine is a twin of Engine 1. It is completely universal.
Images are generated using Gemini Imagen (Nano Banana) with a fallback to Pollinations.ai.
Urdu text is proofread by AI before posting.
"""

import os
import time
import json
import requests
from bs4 import BeautifulSoup
from config.config import get_api_key, get_model_name

# --- AI SDK Imports ---
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from mistralai import Mistral
except ImportError:
    Mistral = None

# ----------------------------------------------------------------------
# Helper: Scrape URL
# ----------------------------------------------------------------------
def scrape_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all('p')])[:4000]
        return text.strip() or "No content."
    except Exception as e:
        return f"Error: {e}"

# ----------------------------------------------------------------------
# Helper: Generate Image using Gemini Imagen (Nano Banana)
# ----------------------------------------------------------------------
def generate_image(image_prompt, gemini_key):
    if not genai or not types or not gemini_key:
        print("❌ Gemini SDK/types or key not available for Imagen.")
        return None

    IMAGEN_MODEL_FALLBACKS = [
        'models/gemini-3.1-flash-image',
        'models/gemini-3.1-flash-lite-image',
        'models/gemini-3-pro-image'
    ]

    client = genai.Client(api_key=gemini_key)
    for model_name in IMAGEN_MODEL_FALLBACKS:
        try:
            print(f"🎨 Trying Nano Banana model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=image_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['image'],
                )
            )
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                        print(f"✅ Image generated successfully with {model_name}.")
                        return part.inline_data.data
            print(f"❌ {model_name} returned no image data. Trying next...")
        except Exception as e:
            print(f"❌ {model_name} failed: {e}. Trying next...")
    
    print("❌ All Nano Banana fallback models failed.")
    return None

# ----------------------------------------------------------------------
# Helper: Generate Image (Pollinations.ai - Fallback)
# ----------------------------------------------------------------------
def generate_pollinations_image(prompt):
    try:
        print("🎨 Falling back to Pollinations.ai...")
        url = f"https://image.pollinations.ai/prompt/{prompt}"
        response = requests.get(url, timeout=45)
        if response.status_code == 200:
            return response.content
        else:
            print(f"❌ Pollinations request failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Pollinations error: {e}")
        return None

# ----------------------------------------------------------------------
# Helper: Proofread Urdu Text using the AI itself
# ----------------------------------------------------------------------
def proofread_text(text, page):
    """
    Sends the generated text back to the AI for proofreading.
    Fixes grammar, spelling, and punctuation WITHOUT changing meaning.
    """
    language = page.get('language', 'English')
    
    # Only proofread if language is Urdu
    if language != "Urdu":
        return text
    
    print("📝 Proofreading Urdu text for grammar mistakes...")
    
    # Build a strict proofreading prompt
    proofread_prompt = f"""You are a strict Urdu grammar editor. Proofread the following Urdu text.
Rules:
1. Fix ONLY spelling mistakes, grammar errors, and punctuation.
2. Do NOT change the meaning, style, or theme.
3. Do NOT add or remove any lines.
4. Do NOT add any explanations or notes.
5. Only return the final corrected text.

Text to proofread:
{text}

Corrected text:"""

    # Use the same provider priority list from the page
    priority_list = page.get('provider_priority', 'gemini').split(',')
    priority_list = [p.strip() for p in priority_list if p.strip()]
    
    for provider in priority_list:
        api_key = get_api_key(provider)
        if not api_key:
            continue
        try:
            if provider == 'groq':
                if not Groq: continue
                model = get_model_name('groq') or 'openai/gpt-oss-120b'
                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": proofread_prompt}]
                )
                corrected = response.choices[0].message.content.strip()
                print(f"✅ Proofreading successful using {provider}")
                return corrected
            else:  # Gemini (or fallback)
                if not genai: continue
                model = get_model_name('gemini') or 'models/gemini-3.5-flash'
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=proofread_prompt
                )
                corrected = response.text.strip()
                print(f"✅ Proofreading successful using {provider}")
                return corrected
        except Exception as e:
            print(f"⚠️ Proofreading with {provider} failed: {e}. Trying next...")
            continue
    
    # If all proofreading fails, return the original text
    print("⚠️ Proofreading failed. Posting original text.")
    return text

# ----------------------------------------------------------------------
# Helper: Post to Facebook (Text + Image OR Text Only)
# ----------------------------------------------------------------------
def post_to_facebook(page, caption, image_bytes=None):
    if image_bytes:
        fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/photos"
        files = {'source': ('image.jpg', image_bytes, 'image/jpeg')}
        data = {'message': caption, 'access_token': page['token']}
    else:
        fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/feed"
        files = None
        data = {'message': caption, 'access_token': page['token']}
    
    if page.get('urls') and page['urls']:
        data['link'] = page['urls'][0]
    
    try:
        if files:
            result = requests.post(fb_url, files=files, data=data).json()
        else:
            result = requests.post(fb_url, data=data).json()
        if 'id' in result:
            print(f"✅ Post successful! ID: {result['id']}")
            return True
        else:
            print(f"❌ FB Error: {result}")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

# ----------------------------------------------------------------------
# MAIN ENGINE 2
# ----------------------------------------------------------------------
def run_engine_2(page):
    """
    Universal Engine 2.
    Generates text, proofreads it, then posts with Gemini Imagen -> Pollinations fallback.
    """
    print(f"🤖 [Engine 2] Running for Page: {page['id']}")

    # --- Load config ---
    CONFIG_FILE = "config.json"
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    google_api_key = config.get('api_keys', {}).get('google_api', '')
    google_engine_id = config.get('api_keys', {}).get('google_engine_id', '')
    search_query = page.get('google_query', '')
    target_urls = page.get('urls', [])
    posts_per_run = page.get('posts_per_run', 2)
    post_interval = page.get('post_interval', 30)
    language = page.get('language', 'English')
    priority_list = page.get('provider_priority', 'gemini').split(',')
    priority_list = [p.strip() for p in priority_list if p.strip()]

    # --- Google Search ---
    if google_api_key and google_engine_id and search_query:
        print(f"🔍 Googling: {search_query}")
        try:
            url = f"https://www.googleapis.com/customsearch/v1?key={google_api_key}&cx={google_engine_id}&q={search_query}&num=5"
            response = requests.get(url).json()
            if 'items' in response:
                for item in response['items']:
                    target_urls.append(item['link'])
        except Exception as e:
            print(f"⚠️ Google Search Error: {e}")

    target_urls = list(set(target_urls))

    # ------------------------------------------------------------------
    # CHECK IF GOOGLE SEARCH IS CONFIGURED
    # ------------------------------------------------------------------
    has_google_search = bool(google_api_key and google_engine_id and search_query)

    # ------------------------------------------------------------------
    # CHECK IF THE BRIEF REQUIRES SCRAPING (SALES, DEALS, ETC.)
    # ------------------------------------------------------------------
    scrape_keywords = ['sale', 'deal', 'scrape', 'find', 'latest', 'promotion', 
                       'discount', 'offer', 'price', 'shop', 'product', 'price drop']
    brief_lower = page.get('brief', '').lower()
    requires_scraping = any(keyword in brief_lower for keyword in scrape_keywords)

    # ------------------------------------------------------------------
    # CRITICAL CHECK: No URLs AND No Google Search AND Brief needs scraping
    # ------------------------------------------------------------------
    if not target_urls and not has_google_search and requires_scraping:
        print("⚠️⚠️⚠️ POST SKIPPED ⚠️⚠️⚠️")
        print("❌ Brief asks to find sales/deals, but there are NO URLs and NO Google Search keys.")
        print("💡 To fix this:")
        print("   1. Add URLs to this page in the Control Panel (under 'URLs'), OR")
        print("   2. Add Google API Key and Search Engine ID in config.json to enable Google Search.")
        print("   3. Or remove 'sale/deal/find' keywords from the Brief if you don't want scraping.")
        return  # <-- EXIT the engine entirely, no fake posts!

    # ----------------------------------------------------------
    # SAFE SCENARIO 1: NO URLs (but brief is safe - poetry, quotes, etc.)
    # ----------------------------------------------------------
    if not target_urls:
        print("ℹ️ No URLs provided. Generating content based purely on the Brief (safe topic).")
        urls_to_process = [None]
        posts_per_run = 1

    # ----------------------------------------------------------
    # SAFE SCENARIO 2: URLs exist (or Google Search is configured)
    # ----------------------------------------------------------
    else:
        max_posts = min(len(target_urls), posts_per_run)
        urls_to_process = target_urls[:max_posts]
        print(f"📋 Processing up to {len(urls_to_process)} URLs")

    posts_made = 0

    for idx, url in enumerate(urls_to_process):
        if url:
            print(f"📡 Scraping: {url}")
            scraped_text = scrape_url(url)
            if "Error" in scraped_text:
                continue
        else:
            print("📝 No URL provided. Using Brief only for content.")
            scraped_text = ""

        # --- Language instruction ---
        lang_instruction = ""
        if language == "Urdu":
            lang_instruction = "Write the post exclusively in Urdu (Nastaleeq style). Use emojis."
        elif language == "English":
            lang_instruction = "Write the post exclusively in English. Use emojis."
        elif language == "Both":
            lang_instruction = "Write the post in both Urdu and English (side by side). Use emojis."
        else:
            lang_instruction = "Write the post in the language that best fits the topic. Use emojis."

        # --- Build prompt ---
        if scraped_text:
            prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nScraped Data: {scraped_text}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"
        else:
            prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"

        formatted_post = None
        image_prompt = None

        # --- AI Provider Loop (Text Generation) ---
        for provider in priority_list:
            api_key = get_api_key(provider)
            if not api_key:
                print(f"⏭️ No key for {provider}, skipping...")
                continue
            try:
                if provider == 'groq':
                    if not Groq: raise Exception("Groq library missing.")
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
                    if not OpenAI: raise Exception("OpenAI library missing.")
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
                    if not OpenAI: raise Exception("OpenAI library missing.")
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
                    if not Anthropic: raise Exception("Anthropic library missing.")
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
                    if not Mistral: raise Exception("Mistral library missing.")
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
                    if not genai: raise Exception("Genai library missing.")
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
                continue

        if not formatted_post:
            print(f"❌ All providers failed for {'URL' if url else 'brief-only'}.")
            continue

        # --- Extract Image Prompt & Clean Text ---
        if formatted_post and "IMAGE_PROMPT:" in formatted_post:
            parts = formatted_post.split("IMAGE_PROMPT:")
            formatted_post = parts[0].strip()
            formatted_post = formatted_post.replace("**", "")  # Remove Markdown
            image_prompt = parts[1].strip()
        else:
            image_prompt = page['brief'] or "A beautiful stock photo"
            if scraped_text:
                image_prompt = scraped_text[:200]

        # --- PROOFREADING (Only for Urdu) ---
        formatted_post = proofread_text(formatted_post, page)

        # ------------------------------------------------------------------
        # CHECK THE BRIEF: SKIP IMAGE?
        # ------------------------------------------------------------------
        skip_image = False
        brief_lower = page.get('brief', '').lower()
        if "no image" in brief_lower or "text only" in brief_lower or "only text" in brief_lower:
            skip_image = True
            print("ℹ️ Brief says 'no image'. Skipping image generation.")
        else:
            print("ℹ️ Brief has no image restriction.")

        # ------------------------------------------------------------------
        # GENERATE IMAGE: Gemini Imagen -> Pollinations.ai Fallback
        # ------------------------------------------------------------------
        image_bytes = None
        if not skip_image:
            gemini_key = get_api_key('gemini')
            if gemini_key:
                print("🎨 Trying Gemini Imagen (Nano Banana)...")
                image_bytes = generate_image(image_prompt, gemini_key)
            
            if not image_bytes:
                print("⚠️ Gemini failed or unavailable. Falling back to Pollinations.ai...")
                image_bytes = generate_pollinations_image(image_prompt)

        # ------------------------------------------------------------------
        # POST TO FACEBOOK
        # ------------------------------------------------------------------
        success = post_to_facebook(page, formatted_post, image_bytes)

        if success:
            posts_made += 1
            if idx < len(urls_to_process) - 1:
                time.sleep(post_interval)

    print(f"🔄 [Engine 2] Finished. Posted {posts_made} posts.")
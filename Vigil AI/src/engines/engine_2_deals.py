"""
engine_2_deals.py - Universal Engine 2 (Load Balancer Worker 2)

This engine is a twin of Engine 1. It is completely universal.
If language is Urdu, it renders text onto an image using Jameel Noori Nastaliq font.
For other languages, it generates creative images via Pollinations.ai.
"""

import os
import time
import json
import requests
from bs4 import BeautifulSoup
from config.config import get_api_key, get_model_name, FONT_PATH, BACKGROUND_IMAGES

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

# --- Urdu Font Rendering Imports ---
try:
    from PIL import Image, ImageDraw, ImageFont
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    arabic_reshaper = None
    get_display = None

# ----------------------------------------------------------------------
# Helper: Reshape Urdu Text
# ----------------------------------------------------------------------
def reshape_urdu_text(text: str) -> str:
    if arabic_reshaper and get_display:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    return text

# ----------------------------------------------------------------------
# Helper: Render Urdu Text to Image (Using Jameel Noori Font)
# ----------------------------------------------------------------------
def render_poetry_to_image(poem_text: str, output_path: str) -> str:
    """Renders Urdu text onto a background image using the Jameel Noori font."""
    if not Image or not ImageDraw or not ImageFont:
        print("❌ PIL libraries missing. Cannot render Urdu image.")
        return None

    import random
    bg_path = None
    if BACKGROUND_IMAGES:
        bg_path = random.choice(BACKGROUND_IMAGES)
    
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path)
    else:
        img = Image.new('RGB', (800, 600), color=(30, 30, 80))
        draw = ImageDraw.Draw(img)
        for i in range(600):
            r = int(30 + (i/600)*50)
            g = int(30 + (i/600)*40)
            b = int(80 + (i/600)*60)
            draw.line([(0,i), (800,i)], fill=(r,g,b))
    
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 45)
    except:
        print(f"⚠️ Font not found at {FONT_PATH}. Using default font.")
        font = ImageFont.load_default()

    lines = [line.strip() for line in poem_text.split('\n') if line.strip()]
    line_spacing = 10
    total_height = sum([draw.textbbox((0,0), line, font=font)[3] + line_spacing for line in lines])
    y_start = (img.height - total_height) // 2

    for i, line in enumerate(lines):
        reshaped_line = reshape_urdu_text(line)
        bbox = draw.textbbox((0,0), reshaped_line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (img.width - text_width) // 2
        y = y_start + i * (bbox[3] + line_spacing)
        draw.text((x+2, y+2), reshaped_line, font=font, fill=(0,0,0))
        draw.text((x, y), reshaped_line, font=font, fill=(255,255,240))

    img.save(output_path)
    print(f"✅ Urdu image saved to {output_path}")
    return output_path

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
# Helper: Generate Image (Pollinations.ai)
# ----------------------------------------------------------------------
def generate_pollinations_image(prompt):
    try:
        print("🎨 Generating image via Pollinations.ai...")
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
# Helper: Post to Facebook (Text + Image OR Text Only)
# ----------------------------------------------------------------------
def post_to_facebook(page, caption, image_bytes=None, image_path=None):
    if image_bytes:
        fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/photos"
        files = {'source': ('image.jpg', image_bytes, 'image/jpeg')}
        data = {'message': caption, 'access_token': page['token']}
    elif image_path and os.path.exists(image_path):
        fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/photos"
        with open(image_path, 'rb') as img:
            files = {'source': img}
            data = {'message': caption, 'access_token': page['token']}
            result = requests.post(fb_url, files=files, data=data).json()
            if 'id' in result:
                print(f"✅ Post successful! ID: {result['id']}")
                return True
            else:
                print(f"❌ FB Error: {result}")
                return False
    else:
        fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/feed"
        files = None
        data = {'message': caption, 'access_token': page['token']}
    
    if page.get('urls') and page['urls']:
        data['link'] = page['urls'][0]
    
    try:
        if files and not image_path:
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
    Universal Engine 2. Works for ANY page.
    If language is Urdu, it renders text with Jameel Noori font.
    Otherwise, it uses standard AI images.
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
    brief = page['brief']
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

    # ----------------------------------------------------------
    # IF NO URLs: Generate content purely from the Brief
    # ----------------------------------------------------------
    if not target_urls:
        print("ℹ️ No URLs provided. Generating content based purely on the Brief.")
        urls_to_process = [None]  # Run the loop once with no URL
        posts_per_run = 1         # Only 1 post when no URL
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

        # --- Build prompt (UNIVERSAL) ---
        if scraped_text:
            prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nScraped Data: {scraped_text}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"
        else:
            prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"

        formatted_post = None
        image_prompt = None

        # --- AI Provider Loop ---
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

        # --- Extract Image Prompt ---
        if formatted_post and "IMAGE_PROMPT:" in formatted_post:
            parts = formatted_post.split("IMAGE_PROMPT:")
            formatted_post = parts[0].strip()
            formatted_post = formatted_post.replace("**", "")   # <-- KILLS THE ASTERISKS
            image_prompt = parts[1].strip()
        else:
            image_prompt = page['brief'] or "A beautiful stock photo"
            if scraped_text:
                image_prompt = scraped_text[:200]

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
        # GENERATE IMAGE
        # ------------------------------------------------------------------
        image_bytes = None
        image_path = None

        if not skip_image:
            # IF LANGUAGE IS URDU: Use Jameel Noori Font Rendering
            if language == "Urdu":
                print("🕌 Language is Urdu. Rendering text with Jameel Noori Nastaliq font...")
                timestamp = int(time.time())
                temp_image_path = os.path.join("data", f"urdu_post_{timestamp}_{idx}.png")
                os.makedirs("data", exist_ok=True)
                
                rendered_path = render_poetry_to_image(formatted_post, temp_image_path)
                if rendered_path:
                    image_path = rendered_path
                else:
                    print("⚠️ Urdu rendering failed. Falling back to Pollinations.ai.")
                    image_bytes = generate_pollinations_image(image_prompt)
            else:
                print("🌍 Language is not Urdu. Using Pollinations.ai for image.")
                image_bytes = generate_pollinations_image(image_prompt)

        # ------------------------------------------------------------------
        # POST TO FACEBOOK
        # ------------------------------------------------------------------
        if image_bytes:
            success = post_to_facebook(page, formatted_post, image_bytes=image_bytes)
        elif image_path:
            success = post_to_facebook(page, formatted_post, image_path=image_path)
        else:
            success = post_to_facebook(page, formatted_post)

        if success:
            posts_made += 1
            if idx < len(urls_to_process) - 1:
                time.sleep(post_interval)

    print(f"🔄 [Engine 2] Finished. Posted {posts_made} posts.")
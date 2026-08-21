import os
import json
import time
import threading
import io
import requests
from flask import Flask, request, render_template_string, redirect, url_for
from bs4 import BeautifulSoup

# --- AI SDK Imports ---
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError as GeminiAPIError
except ImportError:
    genai = None
    types = None
    GeminiAPIError = Exception

try:
    from groq import Groq
    from groq import GroqError as GroqAPIError
except ImportError:
    Groq = None
    GroqAPIError = Exception

try:
    from openai import OpenAI
    from openai import APIError as OpenAIAPIError
except ImportError:
    OpenAI = None
    OpenAIAPIError = Exception

try:
    from anthropic import Anthropic
    from anthropic import APIError as AnthropicAPIError
except ImportError:
    Anthropic = None
    AnthropicAPIError = Exception

try:
    from mistralai import Mistral
    from mistralai import APIError as MistralAPIError
except ImportError:
    Mistral = None
    MistralAPIError = Exception

# Import config functions
from config.config import get_api_key, get_model_name, get_page_token

# --- Import the separate Deals Engine ---
try:
    from src.engines.engine_2_deals import run_engine_2
except ImportError:
    run_engine_2 = None

# --- Configuration ---
CONFIG_FILE = "config.json"

def update_env_token(page_id, new_token):
    """Updates the .env file with a dynamic key based on page_id."""
    env_file = '.env'
    if not os.path.exists(env_file):
        return
    
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    env_key = f"FB_ACCESS_TOKEN_{page_id}"
    updated = False
    
    with open(env_file, 'w') as f:
        for line in lines:
            if line.startswith(f'{env_key}='):
                f.write(f'{env_key}={new_token}\n')
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f'{env_key}={new_token}\n')
    
    print(f"✅ .env file synced: {env_key} updated.")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"api_keys": {}, "pages": [], "daily_requests": {}, "daily_imagen_requests": {}}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Helper to detect poetry pages from the brief
def is_poetry_page(brief):
    poetry_keywords = ['poetry', 'poem', 'urdu', 'shayari', 'nastaleeq', 'verse']
    return any(kw in brief.lower() for kw in poetry_keywords)

# --- Flask App ---
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Vigil AI Control Panel</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 40px auto; padding: 20px; background: #f4f7f6; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h2, h3 { margin-top: 0; }
        input, textarea, select { width: 100%; padding: 8px; margin: 5px 0 15px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        textarea { height: 80px; resize: vertical; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        .btn-warning { background: #ffc107; color: black; }
        .url-row { display: flex; gap: 10px; margin-bottom: 5px; }
        .url-input { flex: 1; }
        .url-list li { background: #eee; padding: 5px 10px; margin-bottom: 5px; display: flex; justify-content: space-between; }
        .edit-form { background: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin-top: 10px; display: none; }
        .provider-list { margin-top: 10px; }
        .provider-item { background: #e9ecef; padding: 8px 12px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .provider-item span { font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 Vigil AI Bot Control Panel</h2>
        <p>Manage your API keys and connected Facebook pages.</p>
    </div>

    <!-- 1. API Key Management -->
    <div class="card" style="background: #fff3cd;">
        <h3>🔑 Manage Your AI API Keys</h3>
        <p>Save a key for a provider. Once saved, it will appear in the "Add Page" dropdown below.</p>
        <form method="POST" action="/add_api_key">
            <label>AI Provider</label>
            <select name="ai_provider" required>
                <option value="gemini">Google Gemini</option>
                <option value="groq">Groq Cloud</option>
                <option value="openai">OpenAI (ChatGPT)</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="mistral">Mistral AI</option>
                <option value="deepseek">DeepSeek</option>
            </select>
            <label>API Key</label>
            <input type="text" name="api_key" required placeholder="Enter your API key for the selected provider...">
            <label>Model Name (Optional - leave blank for default)</label>
            <input type="text" name="model_name" placeholder="e.g. openai/gpt-oss-120b or claude-sonnet-5">
            <button type="submit" class="btn-success" style="width:100%;">💾 Save API Key</button>
        </form>
        <div class="provider-list">
            <strong>Saved API Keys:</strong>
            {% for provider, data in api_keys.items() %}
            <div class="provider-item">
                <span>{{ provider.capitalize() }} (Model: {{ data.model or 'default' }})</span>
                <div>
                    <form method="POST" action="/delete_api_key/{{ provider }}" style="display:inline;">
                        <button type="submit" class="btn-danger" style="padding: 2px 8px; font-size: 12px;">Remove</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- 2. Add New Page -->
    <div class="card" style="background: #e3f2fd;">
        <h3>➕ Add New Facebook Page</h3>
        <form method="POST" action="/add_page">
            <label>Facebook Page ID</label>
            <input type="text" name="page_id" required placeholder="e.g. 123456789">
            <label>Facebook Access Token</label>
            <input type="text" name="page_token" required placeholder="EAAaF...">
            <label>AI Provider (Must have key saved above)</label>
            <select name="ai_provider" required>
                {% if not api_keys %}
                    <option disabled>⚠️ Please save an API key first</option>
                {% else %}
                    {% for provider in api_keys.keys() %}
                        <option value="{{ provider }}">{{ provider.capitalize() }}</option>
                    {% endfor %}
                {% endif %}
            </select>
            <label>Post Language</label>
            <select name="post_language" required>
                <option value="Urdu">Urdu</option>
                <option value="English">English</option>
                <option value="Both">Both (Urdu & English)</option>
                <option value="Auto">Auto-Detect (Based on Brief)</option>
            </select>
            <label>Page Brief / Topic</label>
            <textarea name="brief" required placeholder="e.g. 'I run a small bookstore in Lahore. I want to post daily book recommendations.'"></textarea>
            <label>Provider Priority (comma‑separated, e.g. gemini,groq,openai)</label>
            <input type="text" name="provider_priority" value="gemini" placeholder="gemini,groq,openai">
            <label>Posts per run ...</label>
            <input type="number" name="posts_per_run" value="2" min="1" max="10">
            <label>Post interval ...</label>
            <input type="number" name="post_interval" value="30" min="5" max="300">
            <label>Google Search Query ...</label>
            <input type="text" name="google_query" value="" placeholder="e.g. 'Pakistan sale deals today'">
            <label>Schedule (Post every X hours)</label>
            <input type="number" name="interval_hours" value="2" min="1" max="24" required>
            <button type="submit" class="btn-success" style="width:100%; margin-top:15px;">💾 Save Page & Start Bot</button>
        </form>
    </div>

    <!-- 3. Active Pages List -->
    <div class="card">
        <h3>📋 Your Active Pages ({{ pages|length }})</h3>
        {% if pages %}
            {% for page in pages %}
            <div class="page-item">
                <div><strong>Page ID:</strong> {{ page.id }} | <strong>Interval:</strong> {{ page.interval }} hours</div>
                <div class="meta"><strong>Provider:</strong> {{ page.get('ai_provider', 'gemini').capitalize() }} | <strong>Lang:</strong> {{ page.get('language', 'Urdu') }}</div>
                <div><strong>Brief:</strong> {{ page.brief[:50] }}...</div>
                <div style="margin: 10px 0;">
                    <strong>URLs:</strong>
                    <ul class="url-list">
                        {% for url in page.urls %}
                        <li><span>{{ url }}</span>
                            <form method="POST" action="/remove_url/{{ page.id }}" style="display:inline;">
                                <input type="hidden" name="url_to_remove" value="{{ url }}">
                                <button class="btn-danger" style="padding:2px 8px;">X</button>
                            </form>
                        </li>
                        {% endfor %}
                        <li style="background:none; padding:0;">
                            <form method="POST" action="/add_url/{{ page.id }}" style="display:flex; gap:5px;">
                                <input type="text" name="new_url" placeholder="Add URL" style="flex:1; padding:5px;">
                                <button style="padding:5px 10px;">+</button>
                            </form>
                        </li>
                    </ul>
                    {% if page.google_query %}
                    <div style="margin-top:5px; font-size:12px; color:#555;">
                        <strong>Google Query:</strong> {{ page.google_query }}
                    </div>
                    {% endif %}
                    <div style="font-size:12px; color:#555; margin-top:5px;">
                        <strong>Posts per run:</strong> {{ page.posts_per_run or 2 }} | 
                        <strong>Post interval:</strong> {{ page.post_interval or 30 }}s
                    </div>
                </div>
                <div style="display:flex; gap:10px; margin-top:10px;">
                    <button class="btn-warning" onclick="document.getElementById('edit-form-{{ page.id }}').style.display='block'">✏️ Edit</button>
                    <form method="POST" action="/test_post/{{ page.id }}" style="display:inline;"><button class="btn-success">🟢 Test</button></form>
                    <form method="POST" action="/delete_page/{{ page.id }}" style="display:inline;"><button class="btn-danger">🗑️ Remove</button></form>
                </div>
                <div id="edit-form-{{ page.id }}" class="edit-form">
                    <h4>Edit Page: {{ page.id }}</h4>
                    <form method="POST" action="/edit_page/{{ page.id }}">
                        <label>Access Token</label><input type="text" name="edit_token" value="{{ page.token }}">
                        <label>AI Provider</label>
                        <select name="edit_ai_provider">
                            {% for provider in api_keys.keys() %}
                                <option value="{{ provider }}" {% if page.get('ai_provider') == provider %}selected{% endif %}>{{ provider.capitalize() }}</option>
                            {% endfor %}
                        </select>
                        <label>Language</label>
                        <select name="edit_language">
                            <option value="Urdu" {% if page.get('language') == 'Urdu' %}selected{% endif %}>Urdu</option>
                            <option value="English" {% if page.get('language') == 'English' %}selected{% endif %}>English</option>
                            <option value="Both" {% if page.get('language') == 'Both' %}selected{% endif %}>Both</option>
                            <option value="Auto" {% if page.get('language') == 'Auto' %}selected{% endif %}>Auto-Detect</option>
                        </select>
                        <label>Brief</label><textarea name="edit_brief">{{ page.brief }}</textarea>
                        <label>Provider Priority</label>
                        <input type="text" name="edit_provider_priority" value="{{ page.provider_priority or 'gemini' }}" placeholder="gemini,groq,openai">
                        <label>Posts per run</label>
                        <input type="number" name="edit_posts_per_run" value="{{ page.posts_per_run or 2 }}" min="1" max="10">
                        <label>Post interval (seconds)</label>
                        <input type="number" name="edit_post_interval" value="{{ page.post_interval or 30 }}" min="5" max="300">
                        <label>Google Search Query</label>
                        <input type="text" name="edit_google_query" value="{{ page.google_query or '' }}" placeholder="e.g. 'Pakistan sale deals today'">
                        <label>Interval</label><input type="number" name="edit_interval" value="{{ page.interval }}" min="1">
                        <div style="margin-top:15px; display:flex; gap:10px;">
                            <button type="submit" class="btn-success">💾 Save Changes</button>
                            <button type="button" class="btn-danger" onclick="document.getElementById('edit-form-{{ page.id }}').style.display='none'">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p style="color:#888; text-align:center;">No pages added yet. Add your first page above!</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    config = load_config()
    return render_template_string(HTML_TEMPLATE, api_keys=config.get('api_keys', {}), pages=config.get('pages', []))

@app.route('/add_api_key', methods=['POST'])
def add_api_key():
    config = load_config()
    provider = request.form.get('ai_provider')
    key = request.form.get('api_key').strip()
    model = request.form.get('model_name').strip()
    if 'api_keys' not in config:
        config['api_keys'] = {}
    config['api_keys'][provider] = {'key': key, 'model': model}
    save_config(config)
    return redirect(url_for('index'))

@app.route('/add_google_keys', methods=['POST'])
def add_google_keys():
    config = load_config()
    google_api = request.form.get('google_api', '').strip()
    google_engine_id = request.form.get('google_engine_id', '').strip()
    if 'api_keys' not in config:
        config['api_keys'] = {}
    config['api_keys']['google_api'] = google_api
    config['api_keys']['google_engine_id'] = google_engine_id
    save_config(config)
    return redirect(url_for('index'))

@app.route('/delete_api_key/<provider>', methods=['POST'])
def delete_api_key(provider):
    config = load_config()
    if provider in config.get('api_keys', {}):
        del config['api_keys'][provider]
        save_config(config)
    return redirect(url_for('index'))

@app.route('/add_page', methods=['POST'])
def add_page():
    config = load_config()
    if request.form.get('add_url_action'):
        return redirect(url_for('index'))
    
    page_id = request.form.get('page_id')
    if not any(p['id'] == page_id for p in config['pages']):
        token = request.form.get('page_token')
        config['pages'].append({
            'id': page_id,
            'token': token,
            'ai_provider': request.form.get('ai_provider', 'gemini'),
            'language': request.form.get('post_language', 'Urdu'),
            'brief': request.form.get('brief', ''),
            'urls': [],
            'interval': int(request.form.get('interval_hours', 2)),
            'last_posted': 0,
            'google_query': request.form.get('google_query', ''),
            'provider_priority': request.form.get('provider_priority', 'gemini'),
            'posts_per_run': int(request.form.get('posts_per_run', 2)),
            'post_interval': int(request.form.get('post_interval', 30))
        })
        save_config(config)
        update_env_token(page_id, token)
    return redirect(url_for('index'))

@app.route('/edit_page/<page_id>', methods=['POST'])
def edit_page(page_id):
    config = load_config()
    new_token = None
    for p in config['pages']:
        if p['id'] == page_id:
            new_token = request.form.get('edit_token')
            p['token'] = new_token
            p['ai_provider'] = request.form.get('edit_ai_provider', 'gemini')
            p['language'] = request.form.get('edit_language', 'Urdu')
            p['brief'] = request.form.get('edit_brief')
            p['interval'] = int(request.form.get('edit_interval', 2))
            p['google_query'] = request.form.get('edit_google_query', '')
            p['provider_priority'] = request.form.get('edit_provider_priority', 'gemini')
            p['posts_per_run'] = int(request.form.get('edit_posts_per_run', 2))
            p['post_interval'] = int(request.form.get('edit_post_interval', 30))
            break
    if new_token is not None:
        update_env_token(page_id, new_token)
        save_config(config)
    return redirect(url_for('index'))

@app.route('/add_url/<page_id>', methods=['POST'])
def add_url(page_id):
    config = load_config()
    new_url = request.form.get('new_url', '').strip()
    for p in config['pages']:
        if p['id'] == page_id and new_url and new_url not in p['urls']:
            p['urls'].append(new_url)
            break
    save_config(config)
    return redirect(url_for('index'))

@app.route('/remove_url/<page_id>', methods=['POST'])
def remove_url(page_id):
    config = load_config()
    url_to_remove = request.form.get('url_to_remove')
    for p in config['pages']:
        if p['id'] == page_id and url_to_remove in p['urls']:
            p['urls'].remove(url_to_remove)
            break
    save_config(config)
    return redirect(url_for('index'))

@app.route('/delete_page/<page_id>', methods=['POST'])
def delete_page(page_id):
    config = load_config()
    config['pages'] = [p for p in config['pages'] if p['id'] != page_id]
    save_config(config)
    return redirect(url_for('index'))

# --- Engines ---
def scrape_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all('p')])[:4000]
        return text.strip() or "No content."
    except Exception as e:
        return f"Error: {e}"

def generate_image(image_prompt, gemini_key):
    today = time.strftime("%Y-%m-%d")
    config = load_config()
    daily_imagen = config.get('daily_imagen_requests', {})
    count_today = daily_imagen.get(today, 0)
    
    if count_today >= 500:
        print(f"⛔ Daily Imagen limit reached (500). Skipping Imagen.")
        return None

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
                        image_bytes = part.inline_data.data
                        daily_imagen[today] = count_today + 1
                        config['daily_imagen_requests'] = daily_imagen
                        save_config(config)
                        print(f"✅ Image generated successfully with {model_name}.")
                        return image_bytes
            print(f"❌ {model_name} returned no image data. Trying next...")
        except Exception as e:
            print(f"❌ {model_name} failed: {e}. Trying next...")
    
    print("❌ All Nano Banana fallback models failed.")
    return None

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

def post_to_facebook_with_image(page, caption, image_bytes):
    fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/photos"
    files = {'source': ('image.jpg', io.BytesIO(image_bytes), 'image/jpeg')}
    data = {'message': caption, 'access_token': page['token']}
    if page['urls']:
        data['link'] = page['urls'][0]
    try:
        result = requests.post(fb_url, files=files, data=data).json()
        if 'id' in result:
            print(f"✅ Post with image successful! ID: {result['id']}")
            return True
        else:
            print(f"❌ FB Error (image): {result}")
            return False
    except Exception as e:
        print(f"❌ Connection Error (image): {e}")
        return False

def execute_engine(page):
    # Engine 1 (Poetry) – with dynamic provider priority and model names
    config = load_config()
    print(f"🤖 Running Engine for Page: {page['id']}")
    
    scraped = ""
    if page['urls']:
        scraped = scrape_url(page['urls'][0])
    
    language = page.get('language', 'Urdu')
    brief = page['brief']
    
    lang_instruction = ""
    if language == "Urdu":
        lang_instruction = "Write the post exclusively in Urdu (Nastaleeq style). Use emojis."
    elif language == "English":
        lang_instruction = "Write the post exclusively in English. Use emojis."
    elif language == "Both":
        lang_instruction = "Write the post in both Urdu and English (side by side). Use emojis."
    else:
        lang_instruction = "Write the post in the language that best fits the topic. Use emojis."
    
    if scraped:
        prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nScraped Data: {scraped}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"
    else:
        prompt = f"{lang_instruction}\n\nContext/Brief: {page['brief']}\n\nAlso, return a separate, single sentence in ENGLISH describing an image that represents this text, starting with 'IMAGE_PROMPT:'"

    post_text = None
    image_prompt = None

    # --- Provider Priority Loop (Dynamic models) ---
    priority_list = page.get('provider_priority', 'gemini').split(',')
    priority_list = [p.strip() for p in priority_list if p.strip()]

    for provider in priority_list:
        api_key = get_api_key(provider)
        if not api_key:
            print(f"⏭️ No key for {provider}, skipping...")
            continue
        try:
            if provider == 'groq':
                if not Groq: raise Exception("Groq library missing.")
                model = get_model_name('groq') or 'openai/gpt-oss-120b'  # Dynamic model
                client = Groq(api_key=api_key)
                print(f"🧠 Trying Groq ({model})...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                post_text = response.choices[0].message.content
                print(f"✅ Successfully used {provider}")
                break

            elif provider == 'openai':
                if not OpenAI: raise Exception("OpenAI library missing.")
                model = get_model_name('openai') or 'gpt-4o'  # Dynamic model
                client = OpenAI(api_key=api_key)
                print(f"🧠 Trying OpenAI ({model})...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                post_text = response.choices[0].message.content
                print(f"✅ Successfully used {provider}")
                break

            elif provider == 'deepseek':
                if not OpenAI: raise Exception("OpenAI library missing.")
                model = get_model_name('deepseek') or 'deepseek-chat'  # Dynamic model
                client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                print(f"🧠 Trying DeepSeek ({model})...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                post_text = response.choices[0].message.content
                print(f"✅ Successfully used {provider}")
                break

            elif provider == 'anthropic':
                if not Anthropic: raise Exception("Anthropic library missing.")
                model = get_model_name('anthropic') or 'claude-sonnet-5'  # Dynamic model
                client = Anthropic(api_key=api_key)
                print(f"🧠 Trying Anthropic ({model})...")
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                post_text = response.content[0].text
                print(f"✅ Successfully used {provider}")
                break

            elif provider == 'mistral':
                if not Mistral: raise Exception("Mistral library missing.")
                model = get_model_name('mistral') or 'mistral-medium-2508'  # Dynamic model
                client = Mistral(api_key=api_key)
                print(f"🧠 Trying Mistral ({model})...")
                response = client.chat.complete(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                post_text = response.choices[0].message.content
                print(f"✅ Successfully used {provider}")
                break

            else:  # Gemini
                if not genai: raise Exception("Genai library missing.")
                model = get_model_name('gemini') or 'models/gemini-3.5-flash'  # Dynamic model
                client = genai.Client(api_key=api_key)
                print(f"🧠 Trying Gemini ({model})...")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                post_text = response.text.strip()
                print(f"✅ Successfully used {provider}")
                break

        except Exception as e:
            print(f"❌ {provider} failed: {e}, trying next...")
            continue

    if not post_text:
        print("❌ All providers in priority list failed.")
        post_text = "🚀 Bot encountered AI generation issues. Please check your API keys."

    if post_text and "IMAGE_PROMPT:" in post_text:
        parts = post_text.split("IMAGE_PROMPT:")
        post_text = parts[0].strip()
        image_prompt = parts[1].strip()
    else:
        image_prompt = page['brief'] or "A beautiful stock photo"
        if scraped:
            image_prompt = scraped[:200]

    if not post_text:
        post_text = "🚀 Hello! This is Vigil AI Bot."

    image_bytes = None
    gemini_key = get_api_key('gemini')
    if gemini_key:
        image_bytes = generate_image(image_prompt, gemini_key)
    if not image_bytes:
        image_bytes = generate_pollinations_image(image_prompt)

    if image_bytes:
        return post_to_facebook_with_image(page, post_text, image_bytes)
    else:
        return post_to_facebook_text(post_text, page)

def post_to_facebook_text(post_text, page):
    fb_url = f"https://graph.facebook.com/v26.0/{page['id']}/feed"
    data = {'message': post_text, 'access_token': page['token']}
    if page['urls']:
        data['link'] = page['urls'][0]
    try:
        result = requests.post(fb_url, data=data).json()
        if 'id' in result:
            print(f"✅ Text-only post successful! ID: {result['id']}")
            return True
        else:
            print(f"❌ FB Error (text): {result}")
            return False
    except Exception as e:
        print(f"❌ Connection Error (text): {e}")
        return False

@app.route('/test_post/<page_id>', methods=['POST'])
def test_post(page_id):
    config = load_config()
    for p in config['pages']:
        if p['id'] == page_id:
            print(f"🧪 Test Post for {page_id}...")
            if is_poetry_page(p.get('brief', '')):
                execute_engine(p)   # Engine 1 (Poetry)
            else:
                if run_engine_2:
                    run_engine_2()  # Engine 2 (Text-only)
                else:
                    print("❌ Deals Engine not available.")
            break
    return redirect(url_for('index'))

# --- Scheduler ---
def bot_scheduler():
    while True:
        config = load_config()
        now = time.time()
        for p in config['pages']:
            if (now - p.get('last_posted', 0)) > (p['interval'] * 3600):
                print(f"⏰ Posting for {p['id']}")
                if is_poetry_page(p.get('brief', '')):
                    execute_engine(p)
                else:
                    if run_engine_2:
                        run_engine_2()
                    else:
                        print("❌ Deals Engine not available.")
                p['last_posted'] = now
                save_config(config)
                time.sleep(10)  # 10 seconds gap between pages
        time.sleep(60)

# --- Launcher ---
if __name__ == '__main__':
    print("🚀 Vigil AI Desktop App starting...")
    threading.Thread(target=bot_scheduler, daemon=True).start()
    import webbrowser, time
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://127.0.0.1:5000')
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
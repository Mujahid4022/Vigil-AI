import os
import json
import time
import threading
import requests
from flask import Flask, request, render_template_string, redirect, url_for
from functools import wraps
from flask import Response
from src.engines.engine_engagement import run_engagement

# Import config functions
from config.config import get_api_key, get_model_name, get_page_token

# --- IMPORT THE TWO UNIVERSAL ENGINES ---
from src.engines.engine_1_urdu_poetry import run_engine_1  # Engine 1
from src.engines.engine_2_deals import run_engine_2  # Engine 2

# --- Configuration ---
CONFIG_FILE = "config.json"

def get_facebook_page_name(page_id, access_token):
    """Fetches the actual Facebook Page name using the Graph API."""
    try:
        url = f"https://graph.facebook.com/v26.0/{page_id}?fields=name&access_token={access_token}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get('name', '')
        return None
    except:
        return None


def update_env_token(page_id, new_token):
    """Updates the .env file with a dynamic key based on page_id."""
    env_file = ".env"
    if not os.path.exists(env_file):
        return

    with open(env_file, "r") as f:
        lines = f.readlines()

    env_key = f"FB_ACCESS_TOKEN_{page_id}"
    updated = False

    with open(env_file, "w") as f:
        for line in lines:
            if line.startswith(f"{env_key}="):
                f.write(f"{env_key}={new_token}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"{env_key}={new_token}\n")

    print(f"✅ .env file synced: {env_key} updated.")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # If file doesn't exist, create it with default empty structure
    default_config = {
        "api_keys": {},
        "pages": [],
        "daily_requests": {},
        "daily_imagen_requests": {},
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=4)
    return default_config


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


# --- Flask App ---
app = Flask(__name__)

# ========== GLOBAL BOT STATE ==========
BOT_PAUSED = False

# ========== AUTHENTICATION ==========
USERNAME = "admin"
PASSWORD = "vigilai4042"  # CHANGE THIS!


def check_auth(username, password):
    return username == USERNAME and password == PASSWORD


def authenticate():
    return Response(
        "Login required",
        401,
        {"WWW-Authenticate": 'Basic realm="Vigil AI Control Panel"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


# ========== HTML TEMPLATE ==========
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
    <script>
function toggleUrls(pageId) {
    var list = document.getElementById('urlList-' + pageId);
    var btn = document.getElementById('urlToggleBtn-' + pageId);
    if (list.style.display === 'none') {
        list.style.display = 'block';
        btn.textContent = 'Hide';
    } else {
        list.style.display = 'none';
        btn.textContent = 'Show';
    }
}
</script>
</head>
<body>
    <div class="card">
        <h2>🚀 Vigil AI Bot Control Panel</h2>
        <p>
            Manage your API keys and connected Facebook pages.
            <span style="float:right;">
                <a href="/analytics" target="_blank">📊 View Analytics</a>
            </span>
        </p>
        <div style="display:flex; align-items:center; flex-wrap:wrap; gap:15px; margin-top:10px;">
            <form method="POST" action="/toggle_pause" style="display:inline;">
                <button type="submit" class="btn-warning">
                    {% if bot_paused %}
                        ▶️ Resume Bot
                    {% else %}
                        ⏸️ Pause Bot
                    {% endif %}
                </button>
            </form>
            <span style="font-weight:bold;">
                Status: {% if bot_paused %} 🔴 PAUSED {% else %} 🟢 RUNNING {% endif %}
            </span>
            <a href="/affiliate" style="text-decoration:none; margin-left:auto;">
                <button class="btn-success" style="padding:6px 14px; font-size:14px;">
                    🔗 Go to Affiliate Marketing Dashboard
                </button>
            </a>
        </div>
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
            <label>Facebook Page Name (Optional - for easy identification)</label>
            <input type="text" name="page_name" placeholder="e.g., My Deals Page">
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
            <label>Instagram Account ID (Optional)</label>
            <input type="text" name="instagram_id" placeholder="e.g. 17841412345678901" value="">
            
            <!-- ===== NEW: Per‑Page Twitter & Webhook Fields ===== -->
            <label>Twitter Consumer Key (Optional - for this page)</label>
            <input type="text" name="twitter_consumer_key" placeholder="Your Twitter Consumer Key">
            
            <label>Twitter Consumer Secret</label>
            <input type="text" name="twitter_consumer_secret" placeholder="Your Twitter Consumer Secret">
            
            <label>Twitter Access Token</label>
            <input type="text" name="twitter_access_token" placeholder="Your Twitter Access Token">
            
            <label>Twitter Access Token Secret</label>
            <input type="text" name="twitter_access_token_secret" placeholder="Your Twitter Access Token Secret">
            
            <label>Lead Webhook URL (Optional - for this page)</label>
            <input type="text" name="lead_webhook" placeholder="https://your-zapier-webhook.com">
            <!-- ================================================= -->
            
            <label>Schedule (Post every X hours)</label>
            <input type="number" name="interval_hours" value="2" min="1" max="24" required>
            <button type="submit" class="btn-success" style="width:100%; margin-top:15px;">💾 Save Page & Start Bot</button>
        </form>
    </div>

    <!-- 2.5. Integrations (Twitter, Telegram, Webhooks, Google Search) -->
    <div class="card" style="background: #e8f5e9;">
        <h3>🔗 Integrations (Twitter, Telegram, Webhooks, Google)</h3>
        <p>Paste your API keys for cross-posting, alerts, and Google Search.</p>
        <form method="POST" action="/update_integrations">
            <h4>🐦 Twitter</h4>
            <label>Consumer Key</label><input type="text" name="twitter_consumer_key" value="{{ twitter.consumer_key or '' }}">
            <label>Consumer Secret</label><input type="text" name="twitter_consumer_secret" value="{{ twitter.consumer_secret or '' }}">
            <label>Access Token</label><input type="text" name="twitter_access_token" value="{{ twitter.access_token or '' }}">
            <label>Access Token Secret</label><input type="text" name="twitter_access_token_secret" value="{{ twitter.access_token_secret or '' }}">
            
            <h4>📱 Telegram</h4>
            <label>Bot Token (from @BotFather)</label><input type="text" name="telegram_token" value="{{ telegram_token or '' }}">
            <label>Authorized Telegram User IDs (comma separated)</label>
            <input type="text" name="authorized_users" value="{{ authorized_users or '' }}" placeholder="e.g. 123456789, 987654321">
            
            <h4>🌐 Lead Webhook</h4>
            <label>Webhook URL (Zapier/Mailchimp)</label><input type="text" name="lead_webhook" value="{{ lead_webhook or '' }}">
            
            <button type="submit" class="btn-success" style="width:100%; margin-top:15px;">💾 Save Integrations</button>
        </form>
    </div>

    <!-- 3. Active Pages List -->
    <div class="card">
        <h3>📋 Your Active Pages ({{ pages|length }})</h3>
        {% if pages %}
            {% for page in pages %}
            <div class="page-item">
                <div>
                    <strong>Page Name:</strong> {{ page.get('name', page.id) }} | 
                    <strong>Page ID:</strong> {{ page.id }} | 
                    <strong>Interval:</strong> {{ page.interval }} hours
                </div>
                <div class="meta"><strong>Provider:</strong> {{ page.get('ai_provider', 'gemini').capitalize() }} | <strong>Lang:</strong> {{ page.get('language', 'Urdu') }}</div>
                <div><strong>Brief:</strong> {{ page.brief[:50] }}...</div>
                <div style="margin: 10px 0;">
                    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                        <strong>URLs:</strong>
                        <button onclick="toggleUrls('{{ page.id }}')" id="urlToggleBtn-{{ page.id }}" class="btn-warning" style="padding:2px 10px; font-size:12px;">Show</button>
                    </div>
                    <div id="urlList-{{ page.id }}" style="display:none;">
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
                    </div>
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
                        <label>Page Name</label>
                        <input type="text" name="edit_page_name" value="{{ page.get('name', '') }}" placeholder="e.g., My Deals Page">
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
                        <label>Instagram Account ID</label>
                        <input type="text" name="edit_instagram_id" value="{{ page.get('instagram_account_id', '') }}" placeholder="e.g. 17841412345678901">
                        
                        <!-- ===== NEW: Edit Twitter & Webhook Fields ===== -->
                        <label>Twitter Consumer Key</label>
                        <input type="text" name="edit_twitter_consumer_key" value="{{ page.get('twitter_consumer_key', '') }}">
                        
                        <label>Twitter Consumer Secret</label>
                        <input type="text" name="edit_twitter_consumer_secret" value="{{ page.get('twitter_consumer_secret', '') }}">
                        
                        <label>Twitter Access Token</label>
                        <input type="text" name="edit_twitter_access_token" value="{{ page.get('twitter_access_token', '') }}">
                        
                        <label>Twitter Access Token Secret</label>
                        <input type="text" name="edit_twitter_access_token_secret" value="{{ page.get('twitter_access_token_secret', '') }}">
                        
                        <label>Lead Webhook URL (for this page)</label>
                        <input type="text" name="edit_lead_webhook" value="{{ page.get('lead_webhook_url', '') }}" placeholder="https://your-zapier-webhook.com">
                        <!-- ============================================ -->
                        
                        <label>Interval</label>
                        <input type="number" name="edit_interval" value="{{ page.interval }}" min="1">
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

# ===================== ROUTES =====================


@app.route("/")
@requires_auth
def index():
    config = load_config()
    return render_template_string(
        HTML_TEMPLATE,
        api_keys=config.get("api_keys", {}),
        pages=config.get("pages", []),
        bot_paused=BOT_PAUSED,
        twitter=config.get("twitter_credentials", {}),
        telegram_token=config.get("telegram_bot_token", ""),
        lead_webhook=config.get("lead_webhook_url", ""),
        authorized_users=",".join([str(uid) for uid in config.get("authorized_telegram_users", [])]),
    )


@app.route("/add_api_key", methods=["POST"])
@requires_auth
def add_api_key():
    config = load_config()
    provider = request.form.get("ai_provider")
    key = request.form.get("api_key").strip()
    model = request.form.get("model_name").strip()
    if "api_keys" not in config:
        config["api_keys"] = {}
    config["api_keys"][provider] = {"key": key, "model": model}
    save_config(config)
    return redirect(url_for("index"))


@app.route("/add_google_keys", methods=["POST"])
@requires_auth
def add_google_keys():
    config = load_config()
    google_api = request.form.get("google_api", "").strip()
    google_engine_id = request.form.get("google_engine_id", "").strip()
    if "api_keys" not in config:
        config["api_keys"] = {}
    config["api_keys"]["google_api"] = google_api
    config["api_keys"]["google_engine_id"] = google_engine_id
    save_config(config)
    return redirect(url_for("index"))


@app.route("/delete_api_key/<provider>", methods=["POST"])
@requires_auth
def delete_api_key(provider):
    config = load_config()
    if provider in config.get("api_keys", {}):
        del config["api_keys"][provider]
        save_config(config)
    return redirect(url_for("index"))


@app.route("/add_page", methods=["POST"])
@requires_auth
def add_page():
    config = load_config()
    if request.form.get("add_url_action"):
        return redirect(url_for("index"))

    page_id = request.form.get("page_id")
    if not any(p["id"] == page_id for p in config["pages"]):
        token = request.form.get("page_token")
        config["pages"].append(
            {
                "id": page_id,
                "name": request.form.get("page_name", ""),
                "token": token,
                "ai_provider": request.form.get("ai_provider", "gemini"),
                "language": request.form.get("post_language", "Urdu"),
                "brief": request.form.get("brief", ""),
                "urls": [],
                "interval": int(request.form.get("interval_hours", 2)),
                "last_posted": 0,
                "provider_priority": request.form.get("provider_priority", "gemini"),
                "posts_per_run": int(request.form.get("posts_per_run", 2)),
                "post_interval": int(request.form.get("post_interval", 30)),
                "instagram_account_id": request.form.get("instagram_id", ""),
                # ----- NEW PER‑PAGE FIELDS -----
                "twitter_consumer_key": request.form.get("twitter_consumer_key", ""),
                "twitter_consumer_secret": request.form.get("twitter_consumer_secret", ""),
                "twitter_access_token": request.form.get("twitter_access_token", ""),
                "twitter_access_token_secret": request.form.get("twitter_access_token_secret", ""),
                "lead_webhook_url": request.form.get("lead_webhook", ""),
            }
        )
        save_config(config)
        update_env_token(page_id, token)
    return redirect(url_for("index"))


@app.route("/edit_page/<page_id>", methods=["POST"])
@requires_auth
def edit_page(page_id):
    config = load_config()
    new_token = None
    for p in config["pages"]:
        if p["id"] == page_id:
            new_token = request.form.get("edit_token")
            p["token"] = new_token
            # Auto-fetch the real Facebook Page Name
            real_name = get_facebook_page_name(p["id"], p["token"])
            if real_name:
                p["name"] = real_name
            else:
                p["name"] = request.form.get("edit_page_name", "")
            p["ai_provider"] = request.form.get("edit_ai_provider", "gemini")
            p["language"] = request.form.get("edit_language", "Urdu")
            p["brief"] = request.form.get("edit_brief")
            p["interval"] = int(request.form.get("edit_interval", 2))
            p["provider_priority"] = request.form.get(
                "edit_provider_priority", "gemini"
            )
            p["posts_per_run"] = int(request.form.get("edit_posts_per_run", 2))
            p["post_interval"] = int(request.form.get("edit_post_interval", 30))
            p["instagram_account_id"] = request.form.get("edit_instagram_id", "")
            # ----- NEW PER‑PAGE FIELDS -----
            p["twitter_consumer_key"] = request.form.get("edit_twitter_consumer_key", "")
            p["twitter_consumer_secret"] = request.form.get("edit_twitter_consumer_secret", "")
            p["twitter_access_token"] = request.form.get("edit_twitter_access_token", "")
            p["twitter_access_token_secret"] = request.form.get("edit_twitter_access_token_secret", "")
            p["lead_webhook_url"] = request.form.get("edit_lead_webhook", "")
            break
    if new_token is not None:
        update_env_token(page_id, new_token)
        save_config(config)
    return redirect(url_for("index"))


@app.route("/add_url/<page_id>", methods=["POST"])
@requires_auth
def add_url(page_id):
    config = load_config()
    new_url = request.form.get("new_url", "").strip()
    for p in config["pages"]:
        if p["id"] == page_id and new_url and new_url not in p["urls"]:
            p["urls"].append(new_url)
            break
    save_config(config)
    return redirect(url_for("index"))


@app.route("/remove_url/<page_id>", methods=["POST"])
@requires_auth
def remove_url(page_id):
    config = load_config()
    url_to_remove = request.form.get("url_to_remove")
    for p in config["pages"]:
        if p["id"] == page_id and url_to_remove in p["urls"]:
            p["urls"].remove(url_to_remove)
            break
    save_config(config)
    return redirect(url_for("index"))


@app.route("/delete_page/<page_id>", methods=["POST"])
@requires_auth
def delete_page(page_id):
    config = load_config()
    config["pages"] = [p for p in config["pages"] if p["id"] != page_id]
    save_config(config)
    return redirect(url_for("index"))


@app.route("/update_integrations", methods=["POST"])
@requires_auth
def update_integrations():
    """Saves Twitter, Telegram (with authorized users), Webhook, and Google keys."""
    config = load_config()
    
    # Twitter
    config["twitter_credentials"] = {
        "consumer_key": request.form.get("twitter_consumer_key", ""),
        "consumer_secret": request.form.get("twitter_consumer_secret", ""),
        "access_token": request.form.get("twitter_access_token", ""),
        "access_token_secret": request.form.get("twitter_access_token_secret", ""),
    }
    
    # Telegram Token
    config["telegram_bot_token"] = request.form.get("telegram_token", "")
    
    # Authorized Telegram Users
    auth_users = request.form.get("authorized_users", "").strip()
    if auth_users:
        config["authorized_telegram_users"] = [int(x.strip()) for x in auth_users.split(",") if x.strip()]
    else:
        config["authorized_telegram_users"] = []
    
    # Lead Webhook
    config["lead_webhook_url"] = request.form.get("lead_webhook", "")
       
    save_config(config)
    print("✅ Integrations updated successfully.")
    return redirect(url_for("index"))


# ===================== ANALYTICS DASHBOARD =====================

@app.route("/analytics")
@requires_auth
def analytics():
    """Displays performance analytics from the CSV log."""
    import csv
    import os
    from collections import defaultdict

    log_file = "performance_log.csv"
    if not os.path.exists(log_file):
        return "<h3>No analytics data yet. Run the bot and generate some posts first.</h3>"

    data = []
    with open(log_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    if not data:
        return "<h3>No data rows found.</h3>"

    total_posts = len(data)
    avg_impressions = sum(int(d.get("impressions", 0)) for d in data) / total_posts if total_posts else 0
    avg_likes = sum(int(d.get("likes", 0)) for d in data) / total_posts if total_posts else 0
    avg_comments = sum(int(d.get("comments", 0)) for d in data) / total_posts if total_posts else 0

    page_stats = defaultdict(lambda: {"posts": 0, "impressions": 0, "likes": 0})
    for row in data:
        pid = row.get("page_id", "unknown")
        page_stats[pid]["posts"] += 1
        page_stats[pid]["impressions"] += int(row.get("impressions", 0))
        page_stats[pid]["likes"] += int(row.get("likes", 0))

    html = f"""
    <h2>📊 Vigil AI Performance Dashboard</h2>
    <p><strong>Total Posts Analyzed:</strong> {total_posts}</p>
    <p><strong>Avg Impressions per Post:</strong> {avg_impressions:.1f}</p>
    <p><strong>Avg Likes per Post:</strong> {avg_likes:.1f}</p>
    <p><strong>Avg Comments per Post:</strong> {avg_comments:.1f}</p>
    <hr>
    <h3>📋 Breakdown by Page</h3>
    <ul>
    """
    for pid, stats in page_stats.items():
        html += f"<li><strong>Page {pid}:</strong> {stats['posts']} posts, {stats['impressions']} impressions, {stats['likes']} likes</li>"

    html += """
    </ul>
    <hr>
    <h3>📝 Recent Posts (Last 10)</h3>
    <table border="1" cellpadding="5">
        <tr><th>Time</th><th>Page</th><th>Impressions</th><th>Likes</th><th>Comments</th><th>Shares</th></tr>
    """
    for row in data[-10:]:
        html += f"<tr><td>{row.get('timestamp', '')}</td><td>{row.get('page_id', '')}</td><td>{row.get('impressions', 0)}</td><td>{row.get('likes', 0)}</td><td>{row.get('comments', 0)}</td><td>{row.get('shares', 0)}</td></tr>"

    html += "</table>"
    return html

# ===================== AFFILIATE MARKETING DASHBOARD (BATCH + SCHEDULE) =====================

AFFILIATE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Vigil AI - Affiliate Marketing</title>
    <style>
        body { font-family: Arial; max-width: 1000px; margin: 40px auto; padding: 20px; background: #f4f7f6; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h2, h3 { margin-top: 0; }
        input, textarea, select { width: 100%; padding: 8px; margin: 5px 0 15px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .btn-success { background: #28a745; }
        .btn-danger { background: #dc3545; }
        .btn-warning { background: #ffc107; color: black; }
        .product-card { border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 8px; display: flex; gap: 20px; align-items: flex-start; background: #f9f9f9; }
        .product-image { width: 150px; height: 150px; object-fit: contain; background: white; border-radius: 8px; border: 1px solid #eee; }
        .product-details { flex: 1; }
        .provider-item { background: #e9ecef; padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .queue-item { background: #e3f2fd; padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .back-link { display: inline-block; margin-bottom: 20px; }
        .inline-flex { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        textarea { height: 60px; }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Back to Main Dashboard</a>
    
    <div class="card">
        <h2>🔗 Affiliate Marketing Dashboard (Batch + Schedule)</h2>
        <p>Search for products, preview them, and schedule them for your Facebook pages.</p>
    </div>

    <!-- 1. Add Provider Card -->
    <div class="card" style="background: #e3f2fd;">
        <h3>➕ Add Affiliate Provider</h3>
        <form method="POST" action="/add_provider">
            <label>Provider Name (e.g., Amazon, CJ_Affiliate)</label>
            <input type="text" name="provider_name" required placeholder="Type any name...">
            <label>API Key / Client ID</label>
            <input type="text" name="api_key" placeholder="Your API Key">
            <label>API Secret / Client Secret</label>
            <input type="text" name="api_secret" placeholder="Your API Secret">
            <label>Associate Tag / Campaign ID</label>
            <input type="text" name="associate_tag" placeholder="e.g., yourname-20">
            <button type="submit" class="btn-success" style="width:100%; margin-top:15px;">💾 Save Provider</button>
        </form>
        <h4>Saved Providers:</h4>
        {% for p in providers %}
        <div class="provider-item">
            <span><strong>{{ p.nickname }}</strong></span>
            <form method="POST" action="/delete_provider/{{ p.id }}" style="display:inline;">
                <button type="submit" class="btn-danger" style="padding: 2px 10px;">🗑️ Remove</button>
            </form>
        </div>
        {% else %}
        <p style="color:#888;">No providers added yet.</p>
        {% endfor %}
    </div>

    <!-- 2. Search & Schedule Card -->
    <div class="card" style="background: #fff3cd;">
        <h3>🔍 Batch Product Search & Schedule</h3>
        <form method="POST" action="/search_products">
            <label>Select Facebook Page</label>
            <select name="page_id" required>
                <option value="">-- Select a page --</option>
                {% for page in pages %}
                    <option value="{{ page.id }}">{{ page.get('name', page.id) }}</option>
                {% endfor %}
            </select>
            <label>Select Provider</label>
            <select name="provider_name" required>
                <option value="">-- Select a provider --</option>
                {% for p in providers %}
                    <option value="{{ p.nickname }}">{{ p.nickname }}</option>
                {% endfor %}
            </select>
            <label>Search Term (e.g., "wireless mouse")</label>
            <input type="text" name="search_term" required placeholder="Search for products...">
            <button type="submit" class="btn-success" style="width:100%; margin-top:15px;">🔍 Search & Preview Products</button>
        </form>

        <!-- Display Search Results -->
        {% if search_results %}
        <hr>
        <h3>📦 Product Preview ({{ search_results|length }} found)</h3>
        <form method="POST" action="/schedule_affiliate_posts">
            <input type="hidden" name="page_id" value="{{ current_page_id }}">
            <input type="hidden" name="provider_name" value="{{ current_provider }}">
            <input type="hidden" name="search_term" value="{{ search_term }}">
            
            {% for product in search_results %}
            <div class="product-card">
                <img src="{{ product.image_url }}" alt="{{ product.name }}" class="product-image" onerror="this.src='https://via.placeholder.com/150'">
                <div class="product-details">
                    <strong>{{ product.name }}</strong><br>
                    <strong>Price:</strong> {{ product.price }}<br>
                    <strong>Description:</strong><br>
                    <textarea name="desc_{{ loop.index0 }}">{{ product.description }}</textarea>
                    <div class="inline-flex">
                        <label>Schedule for:</label>
                        <input type="datetime-local" name="time_{{ loop.index0 }}" value="{{ default_time }}" required>
                        <button type="submit" name="schedule_index" value="{{ loop.index0 }}" class="btn-success">📅 Schedule This Product</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </form>
        {% endif %}
    </div>

    <!-- 3. Scheduled Queue -->
    <div class="card">
        <h3>📋 Scheduled Affiliate Posts ({{ scheduled_posts|length }})</h3>
        {% if scheduled_posts %}
            {% for post in scheduled_posts %}
            <div class="queue-item">
                <span><strong>{{ post.search_term }}</strong> | Page: {{ post.page_id }} | Time: {{ post.scheduled_time }}</span>
                <form method="POST" action="/cancel_scheduled/{{ post.id }}" style="display:inline;">
                    <button type="submit" class="btn-danger" style="padding: 2px 10px;">🗑️ Cancel</button>
                </form>
            </div>
            {% endfor %}
        {% else %}
            <p style="color:#888;">Queue is empty. Search and schedule products above!</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/affiliate")
@requires_auth
def affiliate_dashboard():
    config = load_config()
    providers = config.get("affiliate_providers", [])
    pages = config.get("pages", [])
    scheduled = config.get("scheduled_affiliate_posts", [])
    return render_template_string(
        AFFILIATE_HTML,
        providers=providers,
        pages=pages,
        scheduled_posts=scheduled,
        search_results=None,
        current_page_id="",
        current_provider="",
        default_time="",
        search_term=""
    )

@app.route("/search_products", methods=["POST"])
@requires_auth
def search_products():
    from src.utils.affiliate_api import search_products
    config = load_config()
    page_id = request.form.get("page_id")
    provider_name = request.form.get("provider_name")
    search_term = request.form.get("search_term")
    
    # Get provider credentials
    provider = None
    for p in config.get("affiliate_providers", []):
        if p["nickname"] == provider_name:
            provider = p
            break
    
    if not provider:
        return "Provider not found", 400
    
    # Fetch products (Placeholder - will be replaced with real API)
    products = search_products(provider, search_term)
    
    # Re-render the page with results
    providers = config.get("affiliate_providers", [])
    pages = config.get("pages", [])
    scheduled = config.get("scheduled_affiliate_posts", [])
    
    from datetime import datetime, timedelta
    default_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    
    return render_template_string(
        AFFILIATE_HTML,
        providers=providers,
        pages=pages,
        scheduled_posts=scheduled,
        search_results=products,
        current_page_id=page_id,
        current_provider=provider_name,
        default_time=default_time,
        search_term=search_term
    )

@app.route("/schedule_affiliate_posts", methods=["POST"])
@requires_auth
def schedule_affiliate_posts():
    config = load_config()
    if "scheduled_affiliate_posts" not in config:
        config["scheduled_affiliate_posts"] = []
    
    page_id = request.form.get("page_id")
    provider_name = request.form.get("provider_name")
    search_term = request.form.get("search_term")
    schedule_index = request.form.get("schedule_index")
    
    if schedule_index is None or search_term is None:
        return "Missing product data", 400
    
    import uuid
    index = int(schedule_index)
    
    # Get description and time from the form
    desc_key = f"desc_{index}"
    description = request.form.get(desc_key, "")
    time_key = f"time_{index}"
    scheduled_time = request.form.get(time_key)
    
    if not scheduled_time:
        return "Scheduled time is required", 400
    
    # Create scheduled post entry
    new_post = {
        "id": str(uuid.uuid4())[:8],
        "page_id": page_id,
        "provider_name": provider_name,
        "search_term": search_term,
        "description_override": description,
        "scheduled_time": scheduled_time,
        "posted": False,
        "fb_post_id": None
    }
    config["scheduled_affiliate_posts"].append(new_post)
    save_config(config)
    return redirect(url_for("affiliate_dashboard"))

@app.route("/cancel_scheduled/<post_id>", methods=["POST"])
@requires_auth
def cancel_scheduled(post_id):
    config = load_config()
    config["scheduled_affiliate_posts"] = [p for p in config.get("scheduled_affiliate_posts", []) if p["id"] != post_id]
    save_config(config)
    return redirect(url_for("affiliate_dashboard"))

@app.route("/add_provider", methods=["POST"])
@requires_auth
def add_provider():
    config = load_config()
    if "affiliate_providers" not in config:
        config["affiliate_providers"] = []
    import uuid
    provider_id = str(uuid.uuid4())[:8]
    new_provider = {
        "id": provider_id,
        "provider_type": request.form.get("provider_name", "").strip(),
        "nickname": request.form.get("provider_name", "").strip(),
        "api_key": request.form.get("api_key", "").strip(),
        "api_secret": request.form.get("api_secret", "").strip(),
        "associate_tag": request.form.get("associate_tag", "").strip(),
    }
    config["affiliate_providers"].append(new_provider)
    save_config(config)
    return redirect(url_for("affiliate_dashboard"))

@app.route("/delete_provider/<provider_id>", methods=["POST"])
@requires_auth
def delete_provider(provider_id):
    config = load_config()
    config["affiliate_providers"] = [p for p in config.get("affiliate_providers", []) if p["id"] != provider_id]
    save_config(config)
    return redirect(url_for("affiliate_dashboard"))


@app.route("/toggle_pause", methods=["POST"])
@requires_auth
def toggle_pause():
    """Toggles the bot between paused and running states."""
    global BOT_PAUSED
    BOT_PAUSED = not BOT_PAUSED
    status = "paused" if BOT_PAUSED else "resumed"
    print(f"⏸️ Bot {status}")
    return redirect(url_for("index"))


# ===================== TEST & SCHEDULER (ROUND-ROBIN) =====================


@app.route("/test_post/<page_id>", methods=["POST"])
@requires_auth
def test_post(page_id):
    config = load_config()
    pages = config.get("pages", [])
    for idx, p in enumerate(pages):
        if p["id"] == page_id:
            print(f"🧪 Test Post for {page_id}...")
            if idx % 2 == 0:
                print("🔄 Using Engine 1")
                run_engine_1(p)
            else:
                print("🔄 Using Engine 2")
                run_engine_2(p)
            break
    return redirect(url_for("index"))


@app.route("/run_scheduler")
def run_scheduler():
    """UptimeRobot hits this every 5 minutes."""
    config = load_config()
    now = time.time()
    pages = config.get("pages", [])

    for idx, p in enumerate(pages):
        # ---- Posting Logic ----
        if (now - p.get("last_posted", 0)) > (p["interval"] * 3600):
            print(f"⏰ Posting for {p['id']} (Index: {idx})")

            if idx % 2 == 0:
                print("🔄 Using Engine 1")
                run_engine_1(p)
            else:
                print("🔄 Using Engine 2")
                run_engine_2(p)

            p["last_posted"] = now
            save_config(config)
            time.sleep(10)

        # ---- Engagement Logic (once per 24 hours) ----
        engagement_interval = 24 * 3600  # 24 hours
        if (now - p.get("last_engagement", 0)) > engagement_interval:
            print(f"🤝 Running engagement for {p['id']}")
            run_engagement(p)
            p["last_engagement"] = now
            save_config(config)
            time.sleep(5)

    return "Scheduler checked.", 200


# --- Background Scheduler (Round-Robin) ---
def bot_scheduler():
    while True:
        # ---- Check if bot is paused ----
        if BOT_PAUSED:
            print("⏸️ Bot is paused. Waiting...")
            time.sleep(30)
            continue

        config = load_config()
        now = time.time()
        pages = config.get("pages", [])
        
        for idx, p in enumerate(pages):
            # ---- Posting Logic ----
            if (now - p.get("last_posted", 0)) > (p["interval"] * 3600):
                print(f"⏰ Posting for {p['id']} (Index: {idx})")

                if idx % 2 == 0:
                    print("🔄 Using Engine 1")
                    run_engine_1(p)
                else:
                    print("🔄 Using Engine 2")
                    run_engine_2(p)

                p["last_posted"] = now
                save_config(config)
                time.sleep(10)

            # ---- Engagement Logic (once per 24 hours) ----
            engagement_interval = 24 * 3600
            if (now - p.get("last_engagement", 0)) > engagement_interval:
                print(f"🤝 Running engagement for {p['id']}")
                run_engagement(p)
                p["last_engagement"] = now
                save_config(config)
                time.sleep(5)

        # ---- Check Scheduled Affiliate Posts ----
        config = load_config()
        scheduled_posts = config.get("scheduled_affiliate_posts", [])
        now = time.time()
        
        for post in scheduled_posts:
            if post.get("posted"):
                continue
            # Check if time is due (convert string to timestamp)
            try:
                from datetime import datetime
                post_time = datetime.strptime(post["scheduled_time"], "%Y-%m-%dT%H:%M")
                post_timestamp = post_time.timestamp()
                if now >= post_timestamp:
                    print(f"⏰ Affiliate post due for: {post['search_term']}")
                    # We will implement the actual posting logic in the next step
                    # For now, mark as posted to avoid loop
                    post["posted"] = True
                    save_config(config)
                    print(f"✅ Affiliate post would be sent now (placeholder).")
            except Exception as e:
                print(f"⚠️ Error processing scheduled post {post.get('id')}: {e}")

        time.sleep(60)


# --- Launcher ---
if __name__ == "__main__":
    print("🚀 Vigil AI Desktop App starting...")
    
    # Load config for Telegram
    config = load_config()
    telegram_token = config.get("telegram_bot_token", "")
    if telegram_token:
        try:
            from src.core.telegram_bot import start_telegram_bot
            start_telegram_bot(telegram_token)
        except Exception as e:
            print(f"❌ Telegram bot failed to start: {e}")
    else:
        print("ℹ️ No Telegram token found. Bot disabled.")
    
    threading.Thread(target=bot_scheduler, daemon=True).start()
    import webbrowser, time
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
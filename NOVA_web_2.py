# ==============================================================================
# NOVA AI - Web Version 2.0 (Login + Profile + getrennte Chats + SQLite)
# ==============================================================================

from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import json, os, datetime, platform, random, requests, uuid, hashlib, base64, sqlite3

# ------------------------------------------------------------------------------
# !! API KEYS HIER EINTRAGEN !!
# ------------------------------------------------------------------------------
GROQ_API_KEY   = "dein-groq-key-hier"
OPENAI_API_KEY = "dein-openai-key-hier"
# ------------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nova-super-secret-2024-xK9mP3")

# Datenbank-Pfad – auf Railway unter /data, lokal im Home-Verzeichnis
def get_db_path():
    if os.path.exists("/data"):
        return "/data/nova.db"
    if platform.system() == "Darwin":
        d = os.path.expanduser("~/Library/Application Support/NOVA_AI")
    else:
        d = os.path.join(os.path.expanduser("~"), ".nova_ai")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "nova.db")

DB_PATH = get_db_path()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                displayname TEXT NOT NULL,
                avatar_type TEXT DEFAULT 'emoji',
                avatar_data TEXT DEFAULT '🤖',
                settings TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                messages TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

init_db()

PROVIDERS = {
    "Groq":   ["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","gemma2-9b-it"],
    "OpenAI": ["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo"],
    "Ollama": ["llama3","mistral","gemma","phi3"],
}

PERSONALITIES = {
    "de": {
        "🤖 Standard":  "Du bist Nova, eine kluge und hilfreiche KI-Assistentin. Du antwortest präzise, freundlich und auf Deutsch.",
        "😎 Lässig":    "Du bist Nova, eine coole KI. Du redest locker, benutzt Emojis sowie Jugendwörter, kurze knackige Antworten.",
        "🎓 Professor": "Du bist Nova, eine sehr gelehrte KI. Du erklärst alles sehr detailliert auf Deutsch.",
        "😂 Witzig":    "Du bist Nova, eine witzige KI die gerne Witze macht. Antworte auf Deutsch.",
        "🧘 Ruhig":     "Du bist Nova, eine ruhige, bedachte KI. Du antwortest besonnen auf Deutsch.",
        "⚡ Direkt":    "Du bist Nova. Kurz, direkt, auf den Punkt. Antworte auf Deutsch.",
    },
    "en": {
        "🤖 Standard":  "You are Nova, a smart and helpful AI assistant. You answer precisely, friendly, and in English.",
        "😎 Lässig":    "You are Nova, a cool AI. You talk casually, use emojis and slang, short snappy answers in English.",
        "🎓 Professor": "You are Nova, a very knowledgeable AI. You explain everything in great detail in English.",
        "😂 Witzig":    "You are Nova, a funny AI that loves to joke. Answer in English.",
        "🧘 Ruhig":     "You are Nova, a calm and thoughtful AI. You respond with care in English.",
        "⚡ Direkt":    "You are Nova. Short, direct, to the point. Answer in English.",
    },
}

TRANSLATIONS = {
    "de": {
        "placeholder": "Schreib Nova etwas...",
        "new_chat": "➕ Neuer Chat",
        "export": "📤 Chat exportieren",
        "clear_all": "🗑️ Alles löschen",
        "history": "📜 Chat-Verlauf",
        "personality": "🎭 Persönlichkeit",
        "provider": "🧠 KI Anbieter",
        "model": "🤖 Modell",
        "accent": "🎨 Akzentfarbe",
        "language": "🌐 Sprache",
        "variants_question": "✦ Welche Antwort gefällt dir besser?",
        "variant_short": "⚡ Kurz: ",
        "variant_long": "📖 Ausführlich: ",
        "confirm_clear": "Wirklich alle deine Chats löschen?",
        "new_chat_title": "Neuer Chat",
        "thinking": "Nova",
        "error_prefix": "⚠️ Fehler: ",
    },
    "en": {
        "placeholder": "Write Nova something...",
        "new_chat": "➕ New Chat",
        "export": "📤 Export Chat",
        "clear_all": "🗑️ Delete All",
        "history": "📜 Chat History",
        "personality": "🎭 Personality",
        "provider": "🧠 AI Provider",
        "model": "🤖 Model",
        "accent": "🎨 Accent Color",
        "language": "🌐 Language",
        "variants_question": "✦ Which answer do you prefer?",
        "variant_short": "⚡ Short: ",
        "variant_long": "📖 Detailed: ",
        "confirm_clear": "Really delete all your chats?",
        "new_chat_title": "New Chat",
        "thinking": "Nova",
        "error_prefix": "⚠️ Error: ",
    },
}

EMOJIS = ["😀","😎","🤖","🦊","🐱","🐶","🦁","🐼","🐸","🦄","🐙","🦋","🌟","🔥","⚡","🎭","🎨","🎮","🚀","🌈"]

DEFAULT_SETTINGS = {"personality":"🤖 Standard","provider":"Groq","model":"llama-3.3-70b-versatile","accent":"#3B8ED0","language":"de"}

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_user(username):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row: return None
        u = dict(row)
        u["settings"] = json.loads(u["settings"] or "{}")
        if not u["settings"]: u["settings"] = dict(DEFAULT_SETTINGS)
        return u

def save_user(u):
    s = json.dumps(u.get("settings", {}), ensure_ascii=False)
    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (username, password, displayname, avatar_type, avatar_data, settings)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password=excluded.password,
                displayname=excluded.displayname,
                avatar_type=excluded.avatar_type,
                avatar_data=excluded.avatar_data,
                settings=excluded.settings
        """, (u["username"], u["password"], u["displayname"], u["avatar_type"], u["avatar_data"], s))
        conn.commit()

def username_exists(username):
    with get_db() as conn:
        return conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone() is not None

def get_user():
    return session.get("username")

def load_history(username):
    with get_db() as conn:
        rows = conn.execute("SELECT id, messages, created_at FROM chats WHERE username=? ORDER BY created_at ASC", (username,)).fetchall()
        return {row["id"]: json.loads(row["messages"]) for row in rows}

def save_chat(username, cid, messages):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO chats (id, username, messages, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET messages=excluded.messages
        """, (cid, username, json.dumps(messages, ensure_ascii=False), datetime.datetime.now().isoformat()))
        conn.commit()

def delete_chat_db(username, cid):
    with get_db() as conn:
        conn.execute("DELETE FROM chats WHERE id=? AND username=?", (cid, username))
        conn.commit()

def clear_all_chats(username):
    with get_db() as conn:
        conn.execute("DELETE FROM chats WHERE username=?", (username,))
        conn.commit()

def update_setting(username, key, value):
    u = load_user(username)
    if u:
        if "settings" not in u: u["settings"] = dict(DEFAULT_SETTINGS)
        u["settings"][key] = value
        save_user(u)

def ask_groq(messages, model):
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization":f"Bearer {GROQ_API_KEY}","Content-Type":"application/json"},
        json={"model":model,"messages":messages,"max_tokens":1024},timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ask_openai(messages, model):
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
        json={"model":model,"messages":messages,"max_tokens":1024},timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ask_ollama(messages, model):
    import ollama
    return ollama.Client(host='http://127.0.0.1:11434').chat(model=model,messages=messages)['message']['content']

def ask_model(messages, provider, model):
    if provider=="Groq": return ask_groq(messages,model)
    elif provider=="OpenAI": return ask_openai(messages,model)
    elif provider=="Ollama": return ask_ollama(messages,model)
    raise ValueError(f"Unbekannter Anbieter: {provider}")

# ==============================================================================
# AUTH PAGES
# ==============================================================================
AUTH_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>✦ Nova AI – {{ title }}</title>
  <style>
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#0f1117; color:#e8eaf0; min-height:100dvh; display:flex; align-items:center; justify-content:center; padding:20px; }
    .card { background:#161b27; border:1px solid #2a3347; border-radius:20px; padding:40px; width:100%; max-width:420px; }
    h1 { font-size:28px; color:#3B8ED0; margin-bottom:6px; }
    p.sub { color:#8892a4; font-size:14px; margin-bottom:28px; }
    label { font-size:12px; font-weight:600; color:#8892a4; display:block; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.6px; }
    input[type=text], input[type=password] { width:100%; background:#1e2535; border:1px solid #2a3347; color:#e8eaf0; border-radius:10px; padding:12px 14px; font-size:15px; outline:none; margin-bottom:16px; }
    input:focus { border-color:#3B8ED0; }
    .emoji-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin-bottom:16px; }
    .emoji-btn { background:#1e2535; border:2px solid #2a3347; border-radius:10px; font-size:24px; padding:10px; cursor:pointer; transition:all 0.2s; }
    .emoji-btn.selected { border-color:#3B8ED0; background:#1e3a5f; }
    .upload-area { border:2px dashed #2a3347; border-radius:10px; padding:20px; text-align:center; cursor:pointer; margin-bottom:16px; color:#8892a4; font-size:14px; transition:border-color 0.2s; }
    .upload-area:hover { border-color:#3B8ED0; }
    #preview { width:80px; height:80px; border-radius:50%; object-fit:cover; display:none; margin:0 auto 10px; }
    .tab-group { display:flex; background:#1e2535; border-radius:10px; margin-bottom:20px; overflow:hidden; }
    .tab { flex:1; padding:10px; text-align:center; cursor:pointer; font-size:13px; color:#8892a4; border:none; background:transparent; transition:all 0.2s; }
    .tab.active { background:#3B8ED0; color:white; font-weight:600; }
    .btn { width:100%; background:#3B8ED0; color:white; border:none; border-radius:10px; padding:14px; font-size:16px; font-weight:600; cursor:pointer; margin-top:4px; transition:background 0.2s; }
    .btn:hover { background:#36719F; }
    .error { background:#3a1a1a; border:1px solid #602020; border-radius:10px; padding:12px; color:#ff6b6b; font-size:14px; margin-bottom:16px; }
    .link { text-align:center; margin-top:16px; font-size:14px; color:#8892a4; }
    .link a { color:#3B8ED0; text-decoration:none; }
  </style>
</head>
<body>
<div class="card">
  <h1>✦ Nova AI</h1>
  <p class="sub">{{ subtitle }}</p>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST" enctype="multipart/form-data">
    {% if mode == "register" %}
      <label>Benutzername</label>
      <input type="text" name="username" placeholder="z.B. jonte" required>
      <label>Passwort</label>
      <input type="password" name="password" placeholder="Sicheres Passwort" required>
      <label>Anzeigename</label>
      <input type="text" name="displayname" placeholder="z.B. Jonte" required>
      <label>Profilbild</label>
      <div class="tab-group">
        <button type="button" class="tab active" onclick="switchTab('emoji')">😀 Emoji</button>
        <button type="button" class="tab" onclick="switchTab('upload')">📷 Bild</button>
      </div>
      <div id="tab-emoji">
        <div class="emoji-grid">
          {% for e in emojis %}
          <button type="button" class="emoji-btn" onclick="selectEmoji('{{ e }}', this)">{{ e }}</button>
          {% endfor %}
        </div>
        <input type="hidden" name="emoji" id="emoji-input" value="{{ emojis[0] }}">
      </div>
      <div id="tab-upload" style="display:none">
        <img id="preview">
        <div class="upload-area" onclick="document.getElementById('file-input').click()">
          📷 Klick um ein Bild auszuwählen
        </div>
        <input type="file" id="file-input" name="avatar" accept="image/*" style="display:none" onchange="previewImage(this)">
      </div>
      <input type="hidden" name="avatar_type" id="avatar-type" value="emoji">
      <button class="btn" type="submit">Account erstellen</button>
      <div class="link">Schon einen Account? <a href="/login">Einloggen</a></div>
    {% else %}
      <label>Benutzername</label>
      <input type="text" name="username" placeholder="Benutzername" required>
      <label>Passwort</label>
      <input type="password" name="password" placeholder="Passwort" required>
      <button class="btn" type="submit">Einloggen</button>
      <div class="link">Noch kein Account? <a href="/register">Registrieren</a></div>
    {% endif %}
  </form>
</div>
<script>
  function selectEmoji(e, btn) {
    document.querySelectorAll('.emoji-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    document.getElementById('emoji-input').value = e;
  }
  document.querySelector('.emoji-btn')?.classList.add('selected');

  function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-emoji').style.display = tab==='emoji' ? 'block' : 'none';
    document.getElementById('tab-upload').style.display = tab==='upload' ? 'block' : 'none';
    document.getElementById('avatar-type').value = tab;
  }

  function previewImage(input) {
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = e => {
        const img = document.getElementById('preview');
        img.src = e.target.result;
        img.style.display = 'block';
      };
      reader.readAsDataURL(input.files[0]);
    }
  }
</script>
</body>
</html>
"""

# ==============================================================================
# MAIN APP HTML
# ==============================================================================
MAIN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Nova AI">
  <title>✦ Nova AI</title>
  <style>
    * { box-sizing:border-box; margin:0; padding:0; }
    :root {
      --bg:#0f1117; --sidebar:#161b27; --card:#1e2535;
      --accent:{{ user.settings.accent or '#3B8ED0' }};
      --accent2:{{ user.settings.accent or '#3B8ED0' }}cc;
      --text:#e8eaf0; --muted:#8892a4; --border:#2a3347;
      --user-bg:#1e3a5f; --nova-bg:#1e2535; --radius:16px;
    }
    body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text); height:100dvh; display:flex; overflow:hidden; }

    /* SIDEBAR */
    #sidebar { width:280px; background:var(--sidebar); border-right:1px solid var(--border); display:flex; flex-direction:column; transition:transform 0.3s ease; }
    .sidebar-top { padding:16px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; }
    .avatar { width:44px; height:44px; border-radius:50%; border:2px solid var(--accent); display:flex; align-items:center; justify-content:center; font-size:22px; background:var(--card); overflow:hidden; flex-shrink:0; }
    .avatar img { width:100%; height:100%; object-fit:cover; }
    .user-info { flex:1; min-width:0; }
    .user-info strong { display:block; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .user-info span { font-size:11px; color:var(--muted); }
    .logout-btn { background:none; border:none; color:var(--muted); cursor:pointer; font-size:18px; padding:4px; }
    .logout-btn:hover { color:#ff6b6b; }

    .sidebar-section { padding:12px 16px 6px; }
    .sidebar-section label { font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.8px; display:block; margin-bottom:6px; }

    select { width:100%; background:var(--card); border:1px solid var(--border); color:var(--text); border-radius:10px; padding:9px 12px; font-size:13px; outline:none; cursor:pointer; }
    select:focus { border-color:var(--accent); }

    .seg-group { display:flex; background:var(--card); border-radius:10px; border:1px solid var(--border); overflow:hidden; }
    .seg-group button { flex:1; background:transparent; border:none; color:var(--muted); padding:8px 4px; font-size:11px; cursor:pointer; transition:all 0.2s; }
    .seg-group button.active { background:var(--accent); color:white; font-weight:600; }

    /* Akzentfarbe */
    .color-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:4px; }
    .color-dot { width:28px; height:28px; border-radius:50%; cursor:pointer; border:3px solid transparent; transition:all 0.2s; }
    .color-dot.selected { border-color:white; transform:scale(1.15); }

    .btn { display:block; width:100%; background:var(--accent); color:white; border:none; border-radius:10px; padding:10px; font-size:13px; font-weight:600; cursor:pointer; margin-bottom:6px; transition:background 0.2s; }
    .btn:hover { opacity:0.85; }
    .btn.danger { background:#602020; }
    .btn.danger:hover { background:#8B0000; }
    .btn.secondary { background:var(--card); border:1px solid var(--border); color:var(--text); }

    /* Chat-Verlauf */
    .chat-list-wrap { flex:1; overflow-y:auto; padding:6px 10px; scrollbar-width:thin; scrollbar-color:var(--accent) var(--card); }
    .chat-list-wrap::-webkit-scrollbar { width:4px; }
    .chat-list-wrap::-webkit-scrollbar-track { background:var(--card); border-radius:4px; }
    .chat-list-wrap::-webkit-scrollbar-thumb { background:var(--accent); border-radius:4px; }

    .chat-item { display:flex; align-items:center; gap:4px; padding:2px 0; }
    .chat-item button { flex:1; background:transparent; border:none; color:var(--muted); text-align:left; padding:8px 10px; border-radius:8px; font-size:13px; cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .chat-item button:hover { background:var(--card); color:var(--text); }
    .chat-item button.active { background:var(--accent); color:white; }
    .chat-item .del { flex:0; background:transparent; border:none; color:var(--muted); cursor:pointer; font-size:13px; padding:4px 6px; border-radius:6px; }
    .chat-item .del:hover { background:#602020; color:white; }

    /* MAIN */
    #main { flex:1; display:flex; flex-direction:column; overflow:hidden; }
    #topbar { display:none; align-items:center; gap:12px; padding:12px 16px; background:var(--sidebar); border-bottom:1px solid var(--border); }
    #menu-btn { background:none; border:none; color:var(--text); font-size:22px; cursor:pointer; }
    #topbar h2 { font-size:17px; font-weight:700; color:var(--accent); }

    #chat { flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:16px; }
    .msg { display:flex; flex-direction:column; max-width:75%; }
    .msg.user { align-self:flex-end; align-items:flex-end; }
    .msg.nova  { align-self:flex-start; align-items:flex-start; }
    .msg-label { font-size:11px; color:var(--muted); margin-bottom:4px; font-weight:600; display:flex; align-items:center; gap:6px; }
    .msg-avatar { width:20px; height:20px; border-radius:50%; background:var(--card); display:flex; align-items:center; justify-content:center; font-size:12px; overflow:hidden; border:1px solid var(--border); }
    .msg-avatar img { width:100%; height:100%; object-fit:cover; }
    .msg-bubble { padding:12px 16px; border-radius:var(--radius); font-size:15px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
    .msg.user .msg-bubble { background:var(--user-bg); border-bottom-right-radius:4px; }
    .msg.nova .msg-bubble  { background:var(--nova-bg); border-bottom-left-radius:4px; border:1px solid var(--border); }

    .thinking .msg-bubble { display:flex; gap:6px; align-items:center; padding:14px 18px; }
    .dot { width:8px; height:8px; background:var(--accent); border-radius:50%; animation:bounce 1.2s infinite; }
    .dot:nth-child(2) { animation-delay:0.2s; }
    .dot:nth-child(3) { animation-delay:0.4s; }
    @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-8px)} }

    #variants { padding:0 20px 10px; display:flex; flex-direction:column; gap:8px; }
    #variants p { font-size:13px; font-weight:600; color:var(--accent); }
    .variant-btn { background:var(--card); border:1px solid var(--accent); color:var(--text); border-radius:12px; padding:10px 14px; text-align:left; font-size:13px; cursor:pointer; transition:background 0.2s; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .variant-btn:hover { background:var(--accent); }

    #input-area { padding:16px 20px; background:var(--sidebar); border-top:1px solid var(--border); display:flex; gap:10px; align-items:center; }
    #msg-input { flex:1; background:var(--card); border:1px solid var(--border); color:var(--text); border-radius:28px; padding:14px 20px; font-size:15px; outline:none; resize:none; max-height:120px; font-family:inherit; }
    #msg-input:focus { border-color:var(--accent); }
    #send-btn { width:50px; height:50px; background:var(--accent); border:none; border-radius:50%; color:white; font-size:20px; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:opacity 0.2s; }
    #send-btn:hover { opacity:0.85; }

    #overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:10; }

    @media (max-width:700px) {
      #sidebar { position:fixed; top:0; left:0; bottom:0; z-index:20; transform:translateX(-100%); }
      #sidebar.open { transform:translateX(0); }
      #topbar { display:flex; }
      #overlay.show { display:block; }
      .msg { max-width:90%; }
    }
  </style>
</head>
<body>

<!-- SIDEBAR -->
<div id="sidebar">
  <div class="sidebar-top">
    <div class="avatar">
      {% if user.avatar_type == 'image' %}
        <img src="{{ user.avatar_data }}">
      {% else %}
        {{ user.avatar_data or '🤖' }}
      {% endif %}
    </div>
    <div class="user-info">
      <strong>{{ user.displayname }}</strong>
      <span>@{{ user.username }}</span>
    </div>
    <button class="logout-btn" onclick="logout()" title="Ausloggen">⏻</button>
  </div>

  <div class="sidebar-section">
    <label>{{ t.language }}</label>
    <div class="seg-group">
      <button onclick="changeLang('de')" class="{% if user.settings.language == 'de' %}active{% endif %}">🇩🇪 DE</button>
      <button onclick="changeLang('en')" class="{% if user.settings.language == 'en' %}active{% endif %}">🇬🇧 EN</button>
    </div>
  </div>

  <div class="sidebar-section">
    <label>🎭 {{ t.personality }}</label>
    <select onchange="saveSetting('personality', this.value)">
      {% for p in personalities %}
      <option value="{{ p }}" {% if user.settings.personality == p %}selected{% endif %}>{{ p }}</option>
      {% endfor %}
    </select>
  </div>

  <div class="sidebar-section">
    <label>{{ t.provider }}</label>
    <div class="seg-group">
      {% for prov in providers %}
      <button onclick="changeProvider('{{ prov }}')" class="{% if user.settings.provider == prov %}active{% endif %}">{{ prov }}</button>
      {% endfor %}
    </div>
  </div>

  <div class="sidebar-section">
    <label>{{ t.model }}</label>
    <select id="model-sel" onchange="saveSetting('model', this.value)">
      {% for m in providers[user.settings.provider] %}
      <option value="{{ m }}" {% if user.settings.model == m %}selected{% endif %}>{{ m }}</option>
      {% endfor %}
    </select>
  </div>

  <div class="sidebar-section">
    <label>{{ t.accent }}</label>
    <div class="color-row">
      {% for name, color in colors.items() %}
      <div class="color-dot {% if user.settings.accent == color %}selected{% endif %}"
           style="background:{{ color }}"
           onclick="changeAccent('{{ color }}', this)"
           title="{{ name }}"></div>
      {% endfor %}
    </div>
  </div>

  <div class="sidebar-section">
    <button class="btn secondary" onclick="newChat()">{{ t.new_chat }}</button>
    <button class="btn secondary" onclick="exportChat()">{{ t.export }}</button>
    <button class="btn danger" onclick="clearAll()">{{ t.clear_all }}</button>
  </div>

  <div class="sidebar-section">
    <label>{{ t.history }}</label>
  </div>
  <div class="chat-list-wrap">
    <div id="chat-list"></div>
  </div>
</div>

<div id="overlay" onclick="closeSidebar()"></div>

<!-- MAIN -->
<div id="main">
  <div id="topbar">
    <button id="menu-btn" onclick="toggleSidebar()">☰</button>
    <h2>✦ Nova AI</h2>
  </div>
  <div id="chat"></div>
  <div id="variants"></div>
  <div id="input-area">
    <textarea id="msg-input" placeholder="{{ t.placeholder }}" rows="1"
              onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
    <button id="send-btn" onclick="sendMessage()">🚀</button>
  </div>
</div>

<script>
  let currentChatId = null;
  let isThinking    = false;
  let pendingVariants = [];
  const userAvatar = `{% if user.avatar_type == 'image' %}<img src="{{ user.avatar_data }}">{% else %}{{ user.avatar_data or '🤖' }}{% endif %}`;
  const userName   = "{{ user.displayname }}";
  const T = {
    variantsQuestion: "{{ t.variants_question }}",
    variantShort:     "{{ t.variant_short }}",
    variantLong:      "{{ t.variant_long }}",
    confirmClear:     "{{ t.confirm_clear }}",
    newChatTitle:     "{{ t.new_chat_title }}",
    errorPrefix:      "{{ t.error_prefix }}",
  };

  async function changeLang(lang) {
    await saveSetting('language', lang);
    window.location.reload();
  }

  window.onload = async () => {
    await loadChatList();
    newChat();
  };

  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('show');
  }
  function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('overlay').classList.remove('show');
  }

  async function newChat() {
    const r = await fetch('/new_chat', {method:'POST'});
    const d = await r.json();
    currentChatId = d.chat_id;
    document.getElementById('chat').innerHTML = '';
    document.getElementById('variants').innerHTML = '';
    pendingVariants = [];
    await loadChatList();
    closeSidebar();
  }

  async function loadChat(cid) {
    currentChatId = cid;
    const r = await fetch(`/load_chat/${cid}`);
    const d = await r.json();
    const chat = document.getElementById('chat');
    chat.innerHTML = '';
    document.getElementById('variants').innerHTML = '';
    pendingVariants = [];
    for (const m of d.messages) {
      appendMessage(m.sender==='Du'?'user':'nova', m.sender==='Du'?userName:'Nova', m.msg, m.sender==='Du');
    }
    await loadChatList();
    closeSidebar();
  }

  async function loadChatList() {
    const r = await fetch('/chat_list');
    const d = await r.json();
    const list = document.getElementById('chat-list');
    list.innerHTML = '';
    for (const c of d.chats) {
      const div = document.createElement('div');
      div.className = 'chat-item';
      div.innerHTML = `
        <button onclick="loadChat('${c.id}')" class="${c.id===currentChatId?'active':''}">${c.title}</button>
        <button class="del" onclick="deleteChat('${c.id}')">❌</button>
      `;
      list.appendChild(div);
    }
  }

  function appendMessage(role, label, text, isUser) {
    const chat = document.getElementById('chat');
    const div  = document.createElement('div');
    div.className = `msg ${role}`;
    const avatarHtml = isUser
      ? `<div class="msg-avatar">${userAvatar}</div>`
      : `<div class="msg-avatar">✦</div>`;
    div.innerHTML = `
      <div class="msg-label">${avatarHtml} ${escapeHtml(label)}</div>
      <div class="msg-bubble">${escapeHtml(text)}</div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function escapeHtml(t) {
    return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function showThinking() {
    const chat = document.getElementById('chat');
    const div  = document.createElement('div');
    div.className = 'msg nova thinking';
    div.id = 'thinking-bubble';
    div.innerHTML = `<div class="msg-label"><div class="msg-avatar">✦</div> Nova</div><div class="msg-bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }
  function removeThinking() { document.getElementById('thinking-bubble')?.remove(); }

  async function sendMessage() {
    if (isThinking) return;
    const input = document.getElementById('msg-input');
    const text  = input.value.trim();
    if (!text) return;
    document.getElementById('variants').innerHTML = '';
    pendingVariants = [];
    appendMessage('user', userName, text, true);
    input.value = '';
    input.style.height = 'auto';
    isThinking = true;
    showThinking();
    try {
      const r = await fetch('/send', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({message:text, chat_id:currentChatId})
      });
      const d = await r.json();
      removeThinking();
      isThinking = false;
      if (d.variants) { showVariants(d.variants); }
      else { appendMessage('nova','Nova',d.response,false); await loadChatList(); }
    } catch(e) {
      removeThinking(); isThinking = false;
      appendMessage('nova','Nova','⚠️ Fehler: '+e.message,false);
    }
  }

  function showVariants(variants) {
    pendingVariants = variants;
    const div = document.getElementById('variants');
    div.innerHTML = `<p>${T.variantsQuestion}</p>`;
    variants.forEach((v,i) => {
      const btn = document.createElement('button');
      btn.className = 'variant-btn';
      btn.textContent = (i===0 ? T.variantShort : T.variantLong) + v.substring(0,80) + (v.length>80?'…':'');
      btn.onclick = () => pickVariant(i);
      div.appendChild(btn);
    });
  }

  async function pickVariant(idx) {
    const chosen = pendingVariants[idx];
    document.getElementById('variants').innerHTML = '';
    pendingVariants = [];
    await fetch('/pick_variant', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({idx, chat_id:currentChatId, chosen})
    });
    appendMessage('nova','Nova',chosen,false);
    await loadChatList();
  }

  async function saveSetting(key, value) {
    await fetch('/save_setting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,value})});
  }

  async function changeProvider(prov) {
    await saveSetting('provider', prov);
    document.querySelectorAll('.seg-group button').forEach(b => b.classList.toggle('active', b.textContent.trim()===prov));
    const r = await fetch(`/models/${prov}`);
    const d = await r.json();
    const sel = document.getElementById('model-sel');
    sel.innerHTML = d.models.map(m=>`<option value="${m}">${m}</option>`).join('');
    await saveSetting('model', d.models[0]);
  }

  function changeAccent(color, el) {
    document.querySelectorAll('.color-dot').forEach(d=>d.classList.remove('selected'));
    el.classList.add('selected');
    document.documentElement.style.setProperty('--accent', color);
    saveSetting('accent', color);
  }

  async function deleteChat(cid) {
    await fetch(`/delete_chat/${cid}`,{method:'DELETE'});
    if (cid===currentChatId) newChat(); else await loadChatList();
  }

  async function clearAll() {
    if (!confirm(T.confirmClear)) return;
    await fetch('/clear_all',{method:'POST'});
    newChat();
  }

  async function exportChat() {
    const r = await fetch(`/export/${currentChatId}`);
    const d = await r.json();
    const blob = new Blob([d.text],{type:'text/plain'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `Nova_Chat_${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
  }

  async function logout() {
    await fetch('/logout',{method:'POST'});
    window.location.href = '/login';
  }

  function handleKey(e) { if (e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} }
  function autoResize(el) { el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,120)+'px'; }
</script>
</body>
</html>
"""

COLORS = {
    "Blau": "#3B8ED0", "Pink": "#F55AA8", "Grün": "#2ECC71",
    "Orange": "#E67E22", "Lila": "#9B59B6", "Rot": "#E74C3C",
}

# ==============================================================================
# ROUTEN
# ==============================================================================

@app.route("/")
def index():
    if not get_user(): return redirect("/login")
    user = load_user(get_user())
    if not user: return redirect("/login")
    if "settings" not in user or not user["settings"]: user["settings"] = dict(DEFAULT_SETTINGS)
    lang = user["settings"].get("language", "de")
    t    = TRANSLATIONS[lang]
    personalities = list(PERSONALITIES[lang].keys())
    return render_template_string(MAIN_HTML, user=user,
        personalities=personalities,
        providers=PROVIDERS, colors=COLORS, t=t)

@app.route("/register", methods=["GET","POST"])
def register():
    error = None
    if request.method == "POST":
        username    = request.form.get("username","").strip().lower()
        password    = request.form.get("password","")
        displayname = request.form.get("displayname","").strip()
        avatar_type = request.form.get("avatar_type","emoji")
        emoji       = request.form.get("emoji","🤖")
        if not username or not password or not displayname:
            error = "Bitte alle Felder ausfüllen!"
        elif username_exists(username):
            error = "Benutzername bereits vergeben!"
        else:
            avatar_data = emoji
            if avatar_type == "upload":
                f = request.files.get("avatar")
                if f and f.filename:
                    data = f.read()
                    b64  = base64.b64encode(data).decode()
                    mime = f.content_type or "image/jpeg"
                    avatar_data  = f"data:{mime};base64,{b64}"
                    avatar_type  = "image"
                else:
                    avatar_type = "emoji"
            save_user({
                "username": username, "password": hash_pw(password),
                "displayname": displayname, "avatar_type": avatar_type,
                "avatar_data": avatar_data, "settings": dict(DEFAULT_SETTINGS),
            })
            session["username"] = username
            return redirect("/")
    return render_template_string(AUTH_HTML, mode="register", title="Registrieren",
        subtitle="Erstelle deinen Nova Account", error=error, emojis=EMOJIS)

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username","").strip().lower()
        password = request.form.get("password","")
        u = load_user(username)
        if not u or u["password"] != hash_pw(password):
            error = "Falscher Benutzername oder Passwort!"
        else:
            session["username"] = username
            return redirect("/")
    return render_template_string(AUTH_HTML, mode="login", title="Login",
        subtitle="Willkommen zurück bei Nova AI", error=error, emojis=EMOJIS)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/new_chat", methods=["POST"])
def new_chat():
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    cid = str(datetime.datetime.now().timestamp())
    save_chat(u, cid, [])
    return jsonify({"chat_id": cid})

@app.route("/load_chat/<cid>")
def load_chat(cid):
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    with get_db() as conn:
        row = conn.execute("SELECT messages FROM chats WHERE id=? AND username=?", (cid, u)).fetchone()
    messages = json.loads(row["messages"]) if row else []
    return jsonify({"messages": messages})

@app.route("/chat_list")
def chat_list():
    u = get_user()
    if not u: return jsonify({"chats":[]})
    with get_db() as conn:
        rows = conn.execute("SELECT id, messages FROM chats WHERE username=? ORDER BY created_at DESC", (u,)).fetchall()
    chats = []
    for row in rows:
        msgs  = json.loads(row["messages"])
        first = msgs[0].get("msg","Neuer Chat") if msgs else "Neuer Chat"
        title = (first[:16]+"…") if len(first)>16 else first
        chats.append({"id":row["id"],"title":title})
    return jsonify({"chats":chats})

@app.route("/delete_chat/<cid>", methods=["DELETE"])
def delete_chat(cid):
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    delete_chat_db(u, cid)
    return jsonify({"ok":True})

@app.route("/clear_all", methods=["POST"])
def clear_all():
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    clear_all_chats(u)
    return jsonify({"ok":True})

@app.route("/save_setting", methods=["POST"])
def save_setting():
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    data = request.json
    update_setting(u, data["key"], data["value"])
    return jsonify({"ok":True})

@app.route("/models/<provider>")
def get_models(provider):
    return jsonify({"models": PROVIDERS.get(provider, [])})

@app.route("/export/<cid>")
def export_chat(cid):
    u    = get_user()
    h    = load_history(u) if u else {}
    msgs = h.get(cid,[])
    ts   = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    text = f"Nova AI Chat – {ts}\n{'='*50}\n\n"
    for m in msgs:
        text += f"[{'Du' if m.get('sender')=='Du' else 'Nova'}]\n{m.get('msg','')}\n\n"
    return jsonify({"text":text})

@app.route("/send", methods=["POST"])
def send():
    u = get_user()
    if not u: return jsonify({"response":"⚠️ Nicht eingeloggt!"})
    data     = request.json
    user_msg = data.get("message","")
    chat_id  = data.get("chat_id","")
    user_obj = load_user(u)
    s        = user_obj.get("settings", dict(DEFAULT_SETTINGS)) if user_obj else dict(DEFAULT_SETTINGS)
    # Chat laden
    with get_db() as conn:
        row = conn.execute("SELECT messages FROM chats WHERE id=? AND username=?", (chat_id, u)).fetchone()
    msgs_list = json.loads(row["messages"]) if row else []
    msgs_list.append({"sender":"Du","msg":user_msg})
    save_chat(u, chat_id, msgs_list)
    persona  = s.get("personality","🤖 Standard")
    lang     = s.get("language","de")
    system   = PERSONALITIES[lang].get(persona, list(PERSONALITIES[lang].values())[0])
    provider = s.get("provider","Groq")
    model    = s.get("model","llama-3.3-70b-versatile")
    hist = [
        {"role":"user" if m["sender"]=="Du" else "assistant","content":m["msg"]}
        for m in msgs_list[:-1][-10:]
    ]
    try:
        if random.random() < 0.4:
            variants = []
            styles = {
                "de": ["kurz und direkt", "ausführlicher und erklärend"],
                "en": ["short and direct", "more detailed and explanatory"],
            }
            for style in styles.get(lang, styles["de"]):
                sys_v = system + f"\n\nAntworte jetzt {style}."
                api_msgs = [{"role":"system","content":sys_v},*hist,{"role":"user","content":user_msg}]
                variants.append(ask_model(api_msgs,provider,model))
            return jsonify({"variants":variants})
        else:
            api_msgs = [{"role":"system","content":system},*hist,{"role":"user","content":user_msg}]
            res  = ask_model(api_msgs,provider,model)
            msgs_list.append({"sender":"Nova","msg":res})
            save_chat(u, chat_id, msgs_list)
            return jsonify({"response":res})
    except Exception as e:
        return jsonify({"response":f"⚠️ Fehler: {e}"})

@app.route("/pick_variant", methods=["POST"])
def pick_variant():
    u = get_user()
    if not u: return jsonify({"error":"not logged in"}), 401
    data    = request.json
    chat_id = data.get("chat_id","")
    chosen  = data.get("chosen","")
    with get_db() as conn:
        row = conn.execute("SELECT messages FROM chats WHERE id=? AND username=?", (chat_id, u)).fetchone()
    if row:
        msgs_list = json.loads(row["messages"])
        msgs_list.append({"sender":"Nova","msg":chosen})
        save_chat(u, chat_id, msgs_list)
    return jsonify({"ok":True})

if __name__ == "__main__":
    print("\n✦ Nova AI Web Version 2.0 startet...")
    print("━"*40)
    print("📱 Im Browser öffnen: http://localhost:5000")
    print("🔧 Zum Beenden: CTRL+C")
    print("━"*40+"\n")
    app.run(host="0.0.0.0", port=5000, debug=False)

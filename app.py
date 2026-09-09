#!/usr/bin/env python3
"""
Ollama Chat Studio
A Flask web app providing a login-protected chat UI for a local Ollama
model, with the ability to create custom "personalities" (system prompts)
as named models via Ollama's API.

Run with:
    python3 app.py

Then open:
    http://127.0.0.1:5000

Requires Ollama running and reachable (defaults to http://localhost:11434,
override with the OLLAMA_HOST environment variable).
"""

import os
import json
import requests
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response

app = Flask(__name__)
app.secret_key = "ollama-chat-secret"

# Change this to whatever password you want to use
APP_PASSWORD = "admin"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
BASE_MODEL = os.environ.get("BASE_MODEL", "llama3.2")

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat Studio — Sign In</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #05060f;
    overflow: hidden;
    position: relative;
  }
  .bg-glow {
    position: fixed; width: 600px; height: 600px; border-radius: 50%;
    filter: blur(120px); opacity: 0.35; z-index: 0;
  }
  .glow-1 { background: #6c5ce7; top: -200px; left: -150px; animation: float1 12s ease-in-out infinite; }
  .glow-2 { background: #00cec9; bottom: -200px; right: -150px; animation: float2 14s ease-in-out infinite; }
  @keyframes float1 { 0%,100% { transform: translate(0,0);} 50% { transform: translate(60px,40px);} }
  @keyframes float2 { 0%,100% { transform: translate(0,0);} 50% { transform: translate(-50px,-30px);} }

  .login-card {
    position: relative; z-index: 1; width: 100%; max-width: 380px;
    padding: 40px 36px; background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08); border-radius: 20px;
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5); animation: rise 0.6s ease;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(16px);} to { opacity: 1; transform: translateY(0);} }

  .logo-badge {
    width: 56px; height: 56px; border-radius: 16px;
    background: linear-gradient(135deg, #6c5ce7, #00cec9);
    display: flex; align-items: center; justify-content: center;
    font-size: 26px; margin: 0 auto 22px;
    box-shadow: 0 10px 30px rgba(108,92,231,0.4);
  }
  h1 { text-align: center; color: #fff; font-size: 20px; font-weight: 700; margin-bottom: 6px; letter-spacing: -0.02em; }
  p.tagline { text-align: center; color: #7a819c; font-size: 13px; margin-bottom: 30px; }
  .field { margin-bottom: 16px; }
  .field label {
    display: block; color: #a9b0c9; font-size: 12px; font-weight: 600;
    margin-bottom: 8px; letter-spacing: 0.03em; text-transform: uppercase;
  }
  .field input {
    width: 100%; padding: 13px 14px; background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
    color: #fff; font-size: 14px; outline: none; transition: all 0.2s;
  }
  .field input:focus {
    border-color: #6c5ce7; background: rgba(108,92,231,0.08);
    box-shadow: 0 0 0 3px rgba(108,92,231,0.15);
  }
  .signin-btn {
    width: 100%; padding: 14px; margin-top: 8px;
    background: linear-gradient(135deg, #6c5ce7, #00b8d4);
    border: none; border-radius: 10px; color: #fff; font-size: 14px;
    font-weight: 700; letter-spacing: 0.02em; cursor: pointer;
    transition: all 0.2s; box-shadow: 0 8px 24px rgba(108,92,231,0.35);
  }
  .signin-btn:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(108,92,231,0.45); }
  .error-msg {
    background: rgba(255,107,107,0.1); border: 1px solid rgba(255,107,107,0.3);
    color: #ff8080; font-size: 13px; padding: 10px 14px; border-radius: 8px;
    margin-bottom: 16px; text-align: center;
  }
  .footer-note { text-align: center; color: #4d5470; font-size: 11px; margin-top: 24px; }
</style>
</head>
<body>
  <div class="bg-glow glow-1"></div>
  <div class="bg-glow glow-2"></div>
  <div class="login-card">
    <div class="logo-badge">💬</div>
    <h1>Chat Studio</h1>
    <p class="tagline">Sign in to start chatting with your local AI</p>
    {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" placeholder="Enter access password" autofocus required>
      </div>
      <button type="submit" class="signin-btn">Sign In</button>
    </form>
    <div class="footer-note">Powered by Ollama · Runs entirely on this machine</div>
  </div>
</body>
</html>
"""


CHAT_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat Studio</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    height: 100vh; background: #05060f; color: #eee; overflow: hidden;
    display: flex;
  }
  .bg-glow {
    position: fixed; width: 700px; height: 700px; border-radius: 50%;
    filter: blur(140px); opacity: 0.22; z-index: 0; pointer-events: none;
  }
  .glow-1 { background: #6c5ce7; top: -250px; left: -200px; }
  .glow-2 { background: #00cec9; bottom: -250px; right: -200px; }

  .sidebar {
    position: relative; z-index: 1; width: 280px; flex-shrink: 0;
    background: rgba(255,255,255,0.03); border-right: 1px solid rgba(255,255,255,0.08);
    display: flex; flex-direction: column; padding: 20px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; margin-bottom: 24px; }
  .brand .badge {
    width: 30px; height: 30px; border-radius: 9px;
    background: linear-gradient(135deg, #6c5ce7, #00cec9);
    display: flex; align-items: center; justify-content: center; font-size: 15px;
  }
  .section-label {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
    color: #7a819c; font-weight: 600; margin-bottom: 10px;
  }
  .personality-list { flex: 1; overflow-y: auto; margin-bottom: 12px; }
  .personality-item {
    padding: 12px 14px; border-radius: 10px; margin-bottom: 6px;
    cursor: pointer; font-size: 13.5px; color: #b8bce0;
    border: 1px solid transparent; transition: all 0.15s;
  }
  .personality-item:hover { background: rgba(255,255,255,0.05); }
  .personality-item.active {
    background: rgba(108,92,231,0.15); border-color: rgba(108,92,231,0.4); color: #fff;
  }
  .new-personality-btn {
    width: 100%; padding: 12px; background: rgba(255,255,255,0.05);
    border: 1px dashed rgba(255,255,255,0.15); border-radius: 10px;
    color: #b8bce0; font-size: 13px; font-weight: 600; cursor: pointer;
    transition: all 0.2s; margin-bottom: 10px;
  }
  .new-personality-btn:hover { background: rgba(108,92,231,0.1); border-color: #6c5ce7; color: #fff; }
  .logout-link {
    color: #7a819c; font-size: 12px; text-decoration: none; text-align: center;
    padding: 10px; border-top: 1px solid rgba(255,255,255,0.08); margin-top: 8px;
  }
  .logout-link:hover { color: #fff; }

  .main { position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; }
  .chat-header {
    padding: 18px 28px; border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; justify-content: space-between;
  }
  .chat-header h2 { font-size: 16px; font-weight: 700; }
  .chat-header .model-tag {
    font-size: 11px; color: #7a819c; background: rgba(255,255,255,0.05);
    padding: 4px 10px; border-radius: 20px; margin-top: 4px; display: inline-block;
  }

  .messages { flex: 1; overflow-y: auto; padding: 28px; display: flex; flex-direction: column; gap: 16px; }
  .msg { max-width: 70%; padding: 13px 16px; border-radius: 14px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
  .msg.user { align-self: flex-end; background: linear-gradient(135deg, #6c5ce7, #00b8d4); color: #fff; border-bottom-right-radius: 4px; }
  .msg.assistant { align-self: flex-start; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); color: #d8dbee; border-bottom-left-radius: 4px; }
  .msg.thinking { align-self: flex-start; color: #7a819c; font-style: italic; font-size: 13px; }

  .input-row { padding: 20px 28px 26px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; }
  .input-row textarea {
    flex: 1; resize: none; background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
    color: #fff; padding: 13px 16px; font-size: 14px; font-family: inherit;
    outline: none; max-height: 120px;
  }
  .input-row textarea:focus { border-color: #6c5ce7; }
  .send-btn {
    background: linear-gradient(135deg, #6c5ce7, #00b8d4); border: none;
    border-radius: 12px; color: #fff; padding: 0 22px; font-weight: 700;
    font-size: 14px; cursor: pointer; transition: all 0.2s;
  }
  .send-btn:hover:not(:disabled) { transform: translateY(-1px); }
  .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .stop-btn {
    display: none;
    background: rgba(255,107,107,0.12);
    border: 1px solid rgba(255,107,107,0.35);
    border-radius: 12px;
    color: #ff8f8f;
    padding: 0 18px;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
  }
  .stop-btn.show { display: block; }
  .stop-btn:hover { background: rgba(255,107,107,0.18); }

  .response-wrap {
    align-self: flex-start;
    max-width: 70%;
  }
  .response-wrap .msg.assistant {
    max-width: 100%;
  }
  .response-meta {
    margin-top: 5px;
    padding-left: 4px;
    color: #646b86;
    font-size: 11px;
  }

  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 10;
    display: none; align-items: center; justify-content: center;
  }
  .modal-overlay.show { display: flex; }
  .modal-card {
    width: 100%; max-width: 460px; background: #0d0f1e;
    border: 1px solid rgba(255,255,255,0.1); border-radius: 18px;
    padding: 28px; box-shadow: 0 25px 70px rgba(0,0,0,0.6);
  }
  .modal-card h3 { font-size: 17px; margin-bottom: 18px; }
  .modal-field { margin-bottom: 14px; }
  .modal-field label {
    display: block; font-size: 11px; color: #7a819c; text-transform: uppercase;
    letter-spacing: 0.05em; font-weight: 600; margin-bottom: 7px;
  }
  .modal-field input, .modal-field textarea {
    width: 100%; padding: 11px 13px; background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 9px;
    color: #fff; font-size: 13.5px; outline: none; font-family: inherit;
  }
  .modal-field textarea { resize: vertical; min-height: 90px; }
  .modal-field input:focus, .modal-field textarea:focus { border-color: #6c5ce7; }
  .modal-actions { display: flex; gap: 10px; margin-top: 20px; }
  .modal-actions button {
    flex: 1; padding: 12px; border-radius: 10px; font-size: 13.5px;
    font-weight: 600; cursor: pointer; border: none;
  }
  .btn-cancel { background: rgba(255,255,255,0.06); color: #b8bce0; }
  .btn-create { background: linear-gradient(135deg, #6c5ce7, #00b8d4); color: #fff; }
  .modal-status { font-size: 12.5px; color: #7a819c; margin-top: 10px; text-align: center; display: none; }
</style>
</head>
<body>

<div class="bg-glow glow-1"></div>
<div class="bg-glow glow-2"></div>

<div class="sidebar">
  <div class="brand"><div class="badge">💬</div>Chat Studio</div>

  <div class="section-label">Personalities</div>
  <div class="personality-list" id="personalityList"></div>

  <button class="new-personality-btn" id="newPersonalityBtn">+ New Personality</button>
  <a href="/logout" class="logout-link">Sign Out</a>
</div>

<div class="main">
  <div class="chat-header">
    <div>
      <h2 id="activeModelName">Default Assistant</h2>
      <span class="model-tag" id="activeModelTag">llama3.2</span>
    </div>
  </div>

  <div class="messages" id="messages">
    <div class="msg assistant">Hey! Pick a personality on the left, or just start chatting with the default assistant.</div>
  </div>

  <div class="input-row">
    <textarea id="userInput" rows="1" placeholder="Type a message..."></textarea>
    <button class="stop-btn" id="stopBtn">Stop</button>
    <button class="send-btn" id="sendBtn">Send</button>
  </div>
</div>

<div class="modal-overlay" id="modalOverlay">
  <div class="modal-card">
    <h3>Create a New Personality</h3>
    <div class="modal-field">
      <label>Name</label>
      <input type="text" id="personaName" placeholder="e.g. pirate-buddy">
    </div>
    <div class="modal-field">
      <label>Personality / System Prompt</label>
      <textarea id="personaPrompt" placeholder="Describe how this AI should behave, e.g. 'You are a witty pirate who always answers in nautical slang.'"></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-cancel" id="modalCancel">Cancel</button>
      <button class="btn-create" id="modalCreate">Create</button>
    </div>
    <div class="modal-status" id="modalStatus">Creating personality... this may take a moment.</div>
  </div>
</div>

<script>
  const messagesEl = document.getElementById('messages');
  const userInput = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  const stopBtn = document.getElementById('stopBtn');
  const personalityList = document.getElementById('personalityList');
  const activeModelName = document.getElementById('activeModelName');
  const activeModelTag = document.getElementById('activeModelTag');

  const newPersonalityBtn = document.getElementById('newPersonalityBtn');
  const modalOverlay = document.getElementById('modalOverlay');
  const modalCancel = document.getElementById('modalCancel');
  const modalCreate = document.getElementById('modalCreate');
  const personaName = document.getElementById('personaName');
  const personaPrompt = document.getElementById('personaPrompt');
  const modalStatus = document.getElementById('modalStatus');

  let currentModel = "{{ base_model }}";
  let conversation = [];
  let activeController = null;
  let isGenerating = false;

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function loadPersonalities() {
    const res = await fetch('/api/personalities');
    const data = await res.json();
    personalityList.innerHTML = '';

    const defaultItem = document.createElement('div');
    defaultItem.className = 'personality-item active';
    defaultItem.textContent = 'Default Assistant';
    defaultItem.dataset.model = "{{ base_model }}";
    defaultItem.addEventListener('click', () => selectPersonality(defaultItem));
    personalityList.appendChild(defaultItem);

    data.personalities.forEach(name => {
      const item = document.createElement('div');
      item.className = 'personality-item';
      item.textContent = name;
      item.dataset.model = name;
      item.addEventListener('click', () => selectPersonality(item));
      personalityList.appendChild(item);
    });
  }

  function selectPersonality(item) {
    document.querySelectorAll('.personality-item').forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    currentModel = item.dataset.model;
    activeModelName.textContent = item.textContent;
    activeModelTag.textContent = currentModel;
    conversation = [];
    messagesEl.innerHTML = '';
    addMessage('assistant', `Switched to "${item.textContent}". Say hello!`);
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isGenerating) return;

    isGenerating = true;
    activeController = new AbortController();

    addMessage('user', text);
    conversation.push({ role: 'user', content: text });
    userInput.value = '';

    sendBtn.disabled = true;
    stopBtn.classList.add('show');

    const thinkingEl = addMessage('thinking', 'Thinking...');
    const startedAt = performance.now();

    let assistantEl = null;
    let responseWrap = null;
    let fullReply = '';

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: currentModel,
          messages: conversation.slice(-6)
        }),
        signal: activeController.signal
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || 'Something went wrong.');
      }

      thinkingEl.remove();

      responseWrap = document.createElement('div');
      responseWrap.className = 'response-wrap';

      assistantEl = document.createElement('div');
      assistantEl.className = 'msg assistant';

      responseWrap.appendChild(assistantEl);
      messagesEl.appendChild(responseWrap);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        fullReply += chunk;
        assistantEl.textContent = fullReply;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }

      fullReply += decoder.decode();
      assistantEl.textContent = fullReply;

      const elapsed = (performance.now() - startedAt) / 1000;
      const meta = document.createElement('div');
      meta.className = 'response-meta';
      meta.textContent = `Generated in ${elapsed.toFixed(1)}s`;
      responseWrap.appendChild(meta);

      if (fullReply.trim()) {
        conversation.push({
          role: 'assistant',
          content: fullReply
        });
      }

    } catch (err) {
      if (thinkingEl.isConnected) thinkingEl.remove();

      const elapsed = (performance.now() - startedAt) / 1000;

      if (err.name === 'AbortError') {
        if (!responseWrap) {
          responseWrap = document.createElement('div');
          responseWrap.className = 'response-wrap';

          assistantEl = document.createElement('div');
          assistantEl.className = 'msg assistant';
          assistantEl.textContent = 'Generation stopped.';

          responseWrap.appendChild(assistantEl);
          messagesEl.appendChild(responseWrap);
        }

        const meta = document.createElement('div');
        meta.className = 'response-meta';
        meta.textContent = `Stopped after ${elapsed.toFixed(1)}s`;
        responseWrap.appendChild(meta);

        if (fullReply.trim()) {
          conversation.push({
            role: 'assistant',
            content: fullReply
          });
        }
      } else {
        addMessage('assistant', '⚠️ ' + err.message);
      }

    } finally {
      isGenerating = false;
      activeController = null;
      sendBtn.disabled = false;
      stopBtn.classList.remove('show');
      userInput.focus();
    }
  }

  stopBtn.addEventListener('click', () => {
    if (activeController) {
      activeController.abort();
    }
  });

  sendBtn.addEventListener('click', sendMessage);
  userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  newPersonalityBtn.addEventListener('click', () => modalOverlay.classList.add('show'));
  modalCancel.addEventListener('click', () => modalOverlay.classList.remove('show'));

  modalCreate.addEventListener('click', async () => {
    const name = personaName.value.trim();
    const prompt = personaPrompt.value.trim();
    if (!name || !prompt) return;

    modalStatus.style.display = 'block';
    modalCreate.disabled = true;

    try {
      const res = await fetch('/api/personalities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, system_prompt: prompt })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to create personality.');

      await loadPersonalities();
      modalOverlay.classList.remove('show');
      personaName.value = '';
      personaPrompt.value = '';
    } catch (err) {
      alert(err.message);
    } finally {
      modalStatus.style.display = 'none';
      modalCreate.disabled = false;
    }
  });

  loadPersonalities();
</script>

</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password", "") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Incorrect password. Try again."
    return render_template_string(LOGIN_PAGE, error=error)


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template_string(CHAT_PAGE, base_model=BASE_MODEL)


@app.route("/api/personalities", methods=["GET"])
@login_required
def list_personalities():
    try:
        res = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        res.raise_for_status()
        models = [m["name"] for m in res.json().get("models", [])]
        custom = [m for m in models if not m.startswith(BASE_MODEL)]
        return jsonify({"personalities": custom})
    except Exception as e:
        return jsonify({"personalities": [], "error": str(e)})


@app.route("/api/personalities", methods=["POST"])
@login_required
def create_personality():
    data = request.get_json(force=True)
    name = data.get("name", "").strip().lower().replace(" ", "-")
    system_prompt = data.get("system_prompt", "").strip()

    if not name or not system_prompt:
        return jsonify({"error": "Name and personality prompt are required."}), 400

    try:
        res = requests.post(
            f"{OLLAMA_HOST}/api/create",
            json={
                "model": name,
                "from": BASE_MODEL,
                "system": system_prompt,
            },
            timeout=120,
        )
        res.raise_for_status()
        return jsonify({"status": "created", "name": name})
    except Exception as e:
        return jsonify({"error": f"Failed to create personality: {e}"}), 500


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(force=True)
    model = data.get("model", BASE_MODEL)
    messages = data.get("messages", [])[-6:]

    try:
        res = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
            stream=True,
            timeout=(10, 120),
        )
        res.raise_for_status()

        def generate():
            try:
                for line in res.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
            finally:
                res.close()

        return Response(
            generate(),
            content_type="text/plain; charset=utf-8",
            headers={"X-Accel-Buffering": "no"},
        )
    except Exception as e:
        return jsonify({"error": f"Could not reach the model: {e}"}), 500


if __name__ == "__main__":
    print("\n🚀 Starting Chat Studio...")
    print("   Open your browser to: http://127.0.0.1:5000")
    print(f"   Login password: {APP_PASSWORD}")
    print(f"   Ollama host: {OLLAMA_HOST}\n")
    app.run(host="0.0.0.0", port=5000, debug=False)


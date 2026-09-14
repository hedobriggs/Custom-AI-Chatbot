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
import sqlite3
import requests
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response

app = Flask(__name__)
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
if not APP_SECRET_KEY or not APP_PASSWORD:
    raise RuntimeError("APP_SECRET_KEY and APP_PASSWORD must be set in .env")
app.secret_key = APP_SECRET_KEY

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
BASE_MODEL = os.environ.get("BASE_MODEL", "llama3.2")

DB_PATH = os.environ.get("CHAT_DB_PATH", "/app/data/chat_studio.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS personalities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            system_prompt TEXT NOT NULL,
            base_model TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            model TEXT NOT NULL,
            personality_id INTEGER,
            personality_name TEXT,
            system_prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(chats)").fetchall()}
        for column, sql_type in [
            ("personality_id", "INTEGER"),
            ("personality_name", "TEXT"),
            ("system_prompt", "TEXT"),
        ]:
            if column not in columns:
                conn.execute(f"ALTER TABLE chats ADD COLUMN {column} {sql_type}")
        conn.commit()

init_db()

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
<title>Chat Studio — Hedobriggs 😉</title>
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
  .owner-brand { text-align:center; color:#a9b0c9; font-size:12px; margin:5px 0 8px; font-weight:600; }
  .footer-note { text-align: center; color: #4d5470; font-size: 11px; margin-top: 24px; }
</style>
</head>
<body>
  <div class="bg-glow glow-1"></div>
  <div class="bg-glow glow-2"></div>
  <div class="login-card">
    <div class="logo-badge">💬</div>
    <h1>Chat Studio</h1><div class="owner-brand">Hedobriggs 😉</div>
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
  :root {
    --page-bg: #05060f;
    --text: #eee;
    --panel: rgba(255,255,255,0.03);
    --panel-strong: #111426;
    --border: rgba(255,255,255,0.08);
    --muted: #7a819c;
    --message: rgba(255,255,255,0.06);
    --input: rgba(255,255,255,0.05);
  }
  body.light-theme {
    --page-bg: #f6f7fb;
    --text: #171827;
    --panel: rgba(255,255,255,0.88);
    --panel-strong: #ffffff;
    --border: rgba(20,24,45,0.12);
    --muted: #697089;
    --message: #ffffff;
    --input: #ffffff;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    height: 100vh; background: var(--page-bg); color: var(--text); overflow: hidden;
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
    background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 20px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; margin-bottom: 24px; }
  .brand-owner { font-size: 10px; color: #7a819c; font-weight: 500; margin-top: 2px; }
  .brand .badge {
    width: 30px; height: 30px; border-radius: 9px;
    background: linear-gradient(135deg, #6c5ce7, #00cec9);
    display: flex; align-items: center; justify-content: center; font-size: 15px;
  }
  .section-label {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
    color: #7a819c; font-weight: 600; margin-bottom: 10px;
  }
  .personality-list { max-height: 210px; overflow-y: auto; margin-bottom: 12px; }
  .new-chat-btn { width:100%; padding:12px; margin-bottom:18px; background:linear-gradient(135deg,#6c5ce7,#00b8d4); border:none; border-radius:10px; color:#fff; font-weight:700; cursor:pointer; }
  .chat-list { flex:1; overflow-y:auto; margin-bottom:16px; min-height:120px; }
  .chat-item { display:flex; align-items:center; gap:6px; padding:10px 8px 10px 12px; border-radius:9px; margin-bottom:5px; color:#b8bce0; font-size:13px; cursor:pointer; }
  .chat-item:hover,.chat-item.active { background:rgba(108,92,231,.15); color:#fff; }
  .chat-title { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .delete-chat { border:none; background:transparent; color:#646b86; cursor:pointer; font-size:15px; }
  .delete-chat:hover { color:#ff8080; }
  .personality-item {
    padding: 12px 14px; border-radius: 10px; margin-bottom: 6px;
    cursor: pointer; font-size: 13.5px; color: #b8bce0;
    border: 1px solid transparent; transition: all 0.15s;
  }
  .personality-item:hover { background: rgba(255,255,255,0.05); }
  .personality-item.active {
    background: rgba(108,92,231,0.15); border-color: rgba(108,92,231,0.4); color: #fff;
  }
  .personality-control { position: relative; margin-bottom: 12px; }
  .personality-trigger {
    width: 100%; min-height: 42px; display: flex; align-items: center;
    justify-content: space-between; gap: 10px; padding: 10px 12px;
    background: var(--panel-strong); border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); font-size: 13px;
    cursor: pointer; text-align: left;
  }
  .personality-trigger:hover { border-color: rgba(108,92,231,.55); }
  .dropdown-chevron { color: var(--muted); font-size: 17px; line-height: 1; }

  .personality-dropdown {
    display: none; position: absolute; z-index: 50; left: 0; right: 0;
    top: calc(100% + 6px); padding: 5px; max-height: 230px; overflow-y: auto;
    background: var(--panel-strong); border: 1px solid var(--border);
    border-radius: 11px; box-shadow: 0 14px 35px rgba(0,0,0,.28);
  }
  .personality-dropdown.show { display: block; }

  .personality-option {
    position: relative; display: flex; align-items: center; min-height: 38px;
    border-radius: 8px; margin: 2px 0;
  }
  .personality-option:hover { background: var(--input); }
  .personality-option.active { font-weight: 600; }

  .personality-option-name {
    flex: 1; min-width: 0; padding: 10px 42px 10px 10px;
    border: 0; background: transparent; color: var(--text);
    font-size: 12.5px; cursor: pointer; text-align: left;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .persona-menu-button {
    position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
    width: 30px; height: 30px; border: 0; border-radius: 7px;
    background: transparent; color: var(--text); cursor: pointer;
    font-size: 21px; font-weight: 700; line-height: 1;
    display: flex; align-items: center; justify-content: center;
  }
  .persona-menu-button:hover { background: rgba(108,92,231,.18); }

  .persona-action-menu {
    display: none; position: absolute; z-index: 60; right: 4px; top: 34px;
    width: 125px; padding: 5px; background: var(--panel-strong);
    border: 1px solid var(--border); border-radius: 9px;
    box-shadow: 0 10px 28px rgba(0,0,0,.30);
  }
  .persona-action-menu.show { display: block; }

  .persona-action-item {
    width: 100%; display: flex; align-items: center; gap: 9px;
    padding: 8px 9px; border: 0; border-radius: 7px;
    background: transparent; color: var(--text); cursor: pointer;
    font-size: 12.5px; text-align: left;
  }
  .persona-action-item:hover { background: var(--input); }
  .persona-action-item.delete { color: #ff7070; }
  .persona-action-icon {
    width: 19px; height: 19px; display: inline-flex; align-items: center;
    justify-content: center; font-size: 16px; line-height: 1; flex: 0 0 19px;
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
    padding: 10px; border-top: 1px solid var(--border); margin-top: 8px;
  }
  .logout-link:hover { color: #fff; }

  .main { position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; }
  .chat-header {
    padding: 18px 28px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  .chat-header h2 { font-size: 16px; font-weight: 700; }
  .theme-toggle {
    border: 1px solid var(--border); background: var(--input); color: var(--text);
    border-radius: 10px; padding: 9px 12px; cursor: pointer; font-size: 13px;
  }
  .theme-toggle:hover { border-color: #6c5ce7; }

  .chat-header .model-tag {
    font-size: 11px; color: #7a819c; background: rgba(255,255,255,0.05);
    padding: 4px 10px; border-radius: 20px; margin-top: 4px; display: inline-block;
  }

  .messages { flex: 1; overflow-y: auto; padding: 28px; display: flex; flex-direction: column; gap: 16px; }
  .msg { max-width: 70%; padding: 13px 16px; border-radius: 14px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
  .msg.user { align-self: flex-end; background: linear-gradient(135deg, #6c5ce7, #00b8d4); color: #fff; border-bottom-right-radius: 4px; }
  .msg.assistant { align-self: flex-start; background: var(--message); border: 1px solid var(--border); color: var(--text); border-bottom-left-radius: 4px; }
  .msg.thinking { align-self: flex-start; color: #7a819c; font-style: italic; font-size: 13px; }

  .input-row { padding: 20px 28px 26px; border-top: 1px solid var(--border); display: flex; gap: 12px; }
  .input-row textarea {
    flex: 1; resize: none; background: var(--input);
    border: 1px solid var(--border); border-radius: 12px;
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
  .send-btn.generating { display: none; }

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
    width: 100%; padding: 11px 13px; background: var(--input);
    border: 1px solid var(--border); border-radius: 9px;
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
  <div class="brand"><div class="badge">💬</div><div>Chat Studio<div class="brand-owner">Hedobriggs 😉</div></div></div>

  <button class="new-chat-btn" id="newChatBtn">+ New Chat</button>
  <div class="section-label">Chats</div>
  <div class="chat-list" id="chatList"></div>

  <div class="personality-control" id="personalityControl">
    <button class="personality-trigger" id="personalityTrigger" type="button" aria-haspopup="listbox" aria-expanded="false">
      <span id="personalityTriggerName">Personality</span>
      <span class="dropdown-chevron">▼</span>
    </button>
    <div class="personality-dropdown" id="personalityDropdown"></div>
  </div>
  <button class="new-personality-btn" id="newPersonalityBtn">+ New Personality</button>
  <a href="/logout" class="logout-link">Sign Out</a>
</div>

<div class="main">
  <div class="chat-header">
    <div>
      <h2 id="activeModelName">Default Assistant</h2>
      <span class="model-tag" id="activeModelTag">llama3.2</span>
    </div>
    <button class="theme-toggle" id="themeToggle">☀️ Light</button>
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
    <h3 id="personaModalTitle">Create a New Personality</h3>
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
    <div class="modal-status" id="modalStatus">Saving personality...</div>
  </div>
</div>

<script>
  const messagesEl = document.getElementById('messages');
  const userInput = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  const stopBtn = document.getElementById('stopBtn');
  const newChatBtn = document.getElementById('newChatBtn');
  const chatList = document.getElementById('chatList');
  const personalityControl = document.getElementById('personalityControl');
  const personalityTrigger = document.getElementById('personalityTrigger');
  const personalityTriggerName = document.getElementById('personalityTriggerName');
  const personalityDropdown = document.getElementById('personalityDropdown');
  const activeModelName = document.getElementById('activeModelName');
  const activeModelTag = document.getElementById('activeModelTag');
  const themeToggle = document.getElementById('themeToggle');

  const newPersonalityBtn = document.getElementById('newPersonalityBtn');
  const personaModalTitle = document.getElementById('personaModalTitle');
  const modalOverlay = document.getElementById('modalOverlay');
  const modalCancel = document.getElementById('modalCancel');
  const modalCreate = document.getElementById('modalCreate');
  const personaName = document.getElementById('personaName');
  const personaPrompt = document.getElementById('personaPrompt');
  const modalStatus = document.getElementById('modalStatus');

  let currentModel = "{{ base_model }}";
  let currentPersonalityId = null;
  let currentPersonalityName = 'Default Assistant';
  let editingPersonalityId = null;
  let currentChatId = null;
  let conversation = [];
  let activeController = null;
  let isGenerating = false;

  function applyTheme(theme) {
    const isLight = theme === 'light';
    document.body.classList.toggle('light-theme', isLight);
    themeToggle.textContent = isLight ? '🌙 Dark' : '☀️ Light';
    localStorage.setItem('chatStudioTheme', theme);
  }

  themeToggle.addEventListener('click', () => {
    const next = document.body.classList.contains('light-theme') ? 'dark' : 'light';
    applyTheme(next);
  });

  applyTheme(localStorage.getItem('chatStudioTheme') || 'dark');

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function loadChats() {
    const res = await fetch('/api/chats');
    const data = await res.json();
    chatList.innerHTML = '';
    data.chats.forEach(chat => {
      const item = document.createElement('div');
      item.className = 'chat-item' + (chat.id === currentChatId ? ' active' : '');
      const title = document.createElement('span');
      title.className = 'chat-title';
      title.textContent = chat.title;
      title.onclick = () => openChat(chat.id);
      const del = document.createElement('button');
      del.className = 'delete-chat'; del.textContent = '×'; del.title = 'Delete chat';
      del.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete "${chat.title}"?`)) return;
        await fetch(`/api/chats/${chat.id}`, {method:'DELETE'});
        if (currentChatId === chat.id) newChat();
        await loadChats();
      };
      item.append(title, del); chatList.appendChild(item);
    });
  }

  function newChat() {
    if (activeController) activeController.abort();
    currentChatId = null; conversation = []; messagesEl.innerHTML = '';
    addMessage('assistant', 'New chat started. What would you like to talk about?');
    loadChats(); userInput.focus();
  }

  async function openChat(id) {
    if (isGenerating) return;
    const res = await fetch(`/api/chats/${id}`); if (!res.ok) return;
    const data = await res.json();
    currentChatId = data.chat.id;
    currentModel = "{{ base_model }}";
    currentPersonalityId = data.chat.personality_id || null;
    currentPersonalityName = data.chat.personality_name || 'Default Assistant';
    conversation = data.messages.map(m => ({role:m.role, content:m.content}));
    activeModelTag.textContent = currentModel;
    activeModelName.textContent = currentPersonalityName;
    personalityTriggerName.textContent = 'Personality';
    renderPersonalityDropdown();
    messagesEl.innerHTML = ''; data.messages.forEach(m => addMessage(m.role, m.content));
    await loadChats();
  }

  async function ensureChat(prompt) {
    if (currentChatId) return currentChatId;
    const res = await fetch('/api/chats', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({first_prompt:prompt, personality_id:currentPersonalityId})});
    const data = await res.json(); currentChatId = data.id; await loadChats(); return currentChatId;
  }

  async function saveMessage(id, role, content) {
    if (!id || !content.trim()) return;
    await fetch(`/api/chats/${id}/messages`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({role,content})});
    await loadChats();
  }

  let personalities = [];

  async function loadPersonalities() {
    const res = await fetch('/api/personalities');
    const data = await res.json();
    personalities = data.personalities || [];
    renderPersonalityDropdown();
  }

  function closePersonalityMenus() {
    personalityDropdown.classList.remove('show');
    personalityTrigger.setAttribute('aria-expanded', 'false');
    document.querySelectorAll('.persona-action-menu.show').forEach(menu => {
      menu.classList.remove('show');
    });
  }

  function renderPersonalityDropdown() {
    personalityDropdown.innerHTML = '';

    const rows = [
      { id: null, name: 'Default Assistant', isDefault: true },
      ...personalities.map(p => ({ ...p, isDefault: false }))
    ];

    rows.forEach(persona => {
      const row = document.createElement('div');
      row.className = 'personality-option' +
        ((persona.id || null) === currentPersonalityId ? ' active' : '');

      const nameBtn = document.createElement('button');
      nameBtn.type = 'button';
      nameBtn.className = 'personality-option-name';
      nameBtn.textContent =
        ((persona.id || null) === currentPersonalityId ? '✓  ' : '   ') + persona.name;
      nameBtn.title = `Use ${persona.name}`;
      nameBtn.addEventListener('click', () => {
        selectPersonality(persona.id, persona.name);
        closePersonalityMenus();
      });
      row.appendChild(nameBtn);

      if (!persona.isDefault) {
        const dots = document.createElement('button');
        dots.type = 'button';
        dots.className = 'persona-menu-button';
        dots.textContent = '⋮';
        dots.title = `Manage ${persona.name}`;
        dots.setAttribute('aria-label', `Manage ${persona.name}`);

        const menu = document.createElement('div');
        menu.className = 'persona-action-menu';

        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'persona-action-item';
        edit.innerHTML = '<span class="persona-action-icon">✎</span><span>Edit</span>';
        edit.addEventListener('click', async (event) => {
          event.stopPropagation();
          closePersonalityMenus();
          await editPersonality(persona.id);
        });

        const del = document.createElement('button');
        del.type = 'button';
        del.className = 'persona-action-item delete';
        del.innerHTML = '<span class="persona-action-icon">🗑</span><span>Delete</span>';
        del.addEventListener('click', async (event) => {
          event.stopPropagation();
          closePersonalityMenus();
          await deletePersonality(persona.id, persona.name);
        });

        menu.append(edit, del);
        row.append(dots, menu);

        dots.addEventListener('click', (event) => {
          event.stopPropagation();
          const wasOpen = menu.classList.contains('show');
          document.querySelectorAll('.persona-action-menu.show').forEach(m => m.classList.remove('show'));
          if (!wasOpen) menu.classList.add('show');
        });
      }

      personalityDropdown.appendChild(row);
    });
  }

  function selectPersonality(id, label) {
    currentPersonalityId = id ? Number(id) : null;
    currentPersonalityName = label || 'Default Assistant';
    currentModel = "{{ base_model }}";
    personalityTriggerName.textContent = 'Personality';
    activeModelName.textContent = currentPersonalityName;
    activeModelTag.textContent = currentModel;
    currentChatId = null;
    conversation = [];
    messagesEl.innerHTML = '';
    addMessage('assistant', `Switched to "${currentPersonalityName}". A new chat is ready.`);
    renderPersonalityDropdown();
    loadChats();
  }

  personalityTrigger.addEventListener('click', (event) => {
    event.stopPropagation();
    const opening = !personalityDropdown.classList.contains('show');
    closePersonalityMenus();
    if (opening) {
      personalityDropdown.classList.add('show');
      personalityTrigger.setAttribute('aria-expanded', 'true');
    }
  });

  document.addEventListener('click', (event) => {
    if (!personalityControl.contains(event.target)) closePersonalityMenus();
  });

  async function editPersonality(id) {
    const res = await fetch(`/api/personalities/${id}`);
    const data = await res.json();
    if (!res.ok) return alert(data.error || 'Could not load personality.');

    editingPersonalityId = id;
    personaModalTitle.textContent = 'Edit Personality';
    modalCreate.textContent = 'Save Changes';
    personaName.value = data.personality.name;
    personaPrompt.value = data.personality.system_prompt;
    modalOverlay.classList.add('show');
  }

  async function deletePersonality(id, name) {
    if (!confirm(`Delete "${name}"? Existing chats keep their saved personality.`)) return;

    const res = await fetch(`/api/personalities/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) return alert(data.error || 'Could not delete personality.');

    if (currentPersonalityId === id) {
      currentPersonalityId = null;
      currentPersonalityName = 'Default Assistant';
      personalityTriggerName.textContent = 'Personality';
      activeModelName.textContent = currentPersonalityName;
      activeModelTag.textContent = "{{ base_model }}";
    }
    await loadPersonalities();
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isGenerating) return;

    isGenerating = true;
    activeController = new AbortController();

    const chatId = await ensureChat(text);
    addMessage('user', text);
    conversation.push({ role: 'user', content: text });
    await saveMessage(chatId, 'user', text);
    userInput.value = '';

    sendBtn.disabled = true;
    sendBtn.classList.add('generating');
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
          personality_id: currentPersonalityId,
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
        await saveMessage(chatId, 'assistant', fullReply);
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
      sendBtn.classList.remove('generating');
      stopBtn.classList.remove('show');
      userInput.focus();
    }
  }

  stopBtn.addEventListener('click', () => {
    if (activeController) {
      activeController.abort();
    }
  });

  newChatBtn.addEventListener('click', newChat);
  sendBtn.addEventListener('click', sendMessage);
  userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  newPersonalityBtn.addEventListener('click', () => {
    editingPersonalityId = null;
    personaModalTitle.textContent = 'Create a New Personality';
    modalCreate.textContent = 'Create';
    personaName.value = '';
    personaPrompt.value = '';
    modalOverlay.classList.add('show');
  });

  modalCancel.addEventListener('click', () => modalOverlay.classList.remove('show'));

  modalCreate.addEventListener('click', async () => {
    const name = personaName.value.trim();
    const prompt = personaPrompt.value.trim();
    if (!name || !prompt) return alert('Name and personality prompt are required.');
    modalStatus.style.display = 'block';
    modalCreate.disabled = true;
    try {
      const endpoint = editingPersonalityId ? `/api/personalities/${editingPersonalityId}` : '/api/personalities';
      const method = editingPersonalityId ? 'PUT' : 'POST';
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, system_prompt: prompt })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save personality.');
      currentPersonalityId = data.personality.id;
      currentPersonalityName = data.personality.name;
      activeModelName.textContent = currentPersonalityName;
      activeModelTag.textContent = "{{ base_model }}";
      await loadPersonalities();
      modalOverlay.classList.remove('show');
      editingPersonalityId = null;
    } catch (err) {
      alert(err.message);
    } finally {
      modalStatus.style.display = 'none';
      modalCreate.disabled = false;
    }
  });

  loadPersonalities();
  loadChats();
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


@app.route("/api/chats", methods=["GET"])
@login_required
def list_chats():
    with get_db() as conn:
        rows = conn.execute("SELECT id,title,model,personality_id,personality_name,created_at,updated_at FROM chats ORDER BY updated_at DESC,id DESC").fetchall()
    return jsonify({"chats": [dict(r) for r in rows]})

@app.route("/api/chats", methods=["POST"])
@login_required
def create_chat():
    data = request.get_json(force=True)
    prompt = data.get("first_prompt", "").strip()
    personality_id = data.get("personality_id")
    title = " ".join(prompt.split()[:6]) or "New Chat"
    if len(title) > 42:
        title = title[:39].rstrip() + "..."

    personality_name = "Default Assistant"
    system_prompt = None
    with get_db() as conn:
        if personality_id:
            persona = conn.execute(
                "SELECT id,name,system_prompt FROM personalities WHERE id=?", (personality_id,)
            ).fetchone()
            if not persona:
                return jsonify({"error": "Personality not found."}), 404
            personality_id = persona["id"]
            personality_name = persona["name"]
            system_prompt = persona["system_prompt"]

        cur = conn.execute(
            "INSERT INTO chats (title,model,personality_id,personality_name,system_prompt) VALUES (?,?,?,?,?)",
            (title, BASE_MODEL, personality_id, personality_name, system_prompt),
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "title": title, "model": BASE_MODEL,
                    "personality_id": personality_id, "personality_name": personality_name})

@app.route("/api/chats/<int:chat_id>", methods=["GET"])
@login_required
def get_chat(chat_id):
    with get_db() as conn:
        chat = conn.execute("SELECT id,title,model,personality_id,personality_name,system_prompt,created_at,updated_at FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not chat: return jsonify({"error":"Chat not found."}),404
        msgs = conn.execute("SELECT role,content,created_at FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return jsonify({"chat":dict(chat), "messages":[dict(m) for m in msgs]})

@app.route("/api/chats/<int:chat_id>/messages", methods=["POST"])
@login_required
def save_chat_message(chat_id):
    data=request.get_json(force=True); role=data.get("role",""); content=data.get("content","").strip()
    if role not in {"user","assistant"} or not content: return jsonify({"error":"Invalid message."}),400
    with get_db() as conn:
        conn.execute("INSERT INTO messages (chat_id,role,content) VALUES (?,?,?)",(chat_id,role,content))
        conn.execute("UPDATE chats SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(chat_id,))
        conn.commit()
    return jsonify({"status":"saved"})

@app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id=?",(chat_id,))
        conn.execute("DELETE FROM chats WHERE id=?",(chat_id,))
        conn.commit()
    return jsonify({"status":"deleted"})


@app.route("/api/personalities", methods=["GET"])
@login_required
def list_personalities():
    with get_db() as conn:
        rows = conn.execute("SELECT id,name,base_model FROM personalities ORDER BY name COLLATE NOCASE").fetchall()
    return jsonify({"personalities": [dict(row) for row in rows]})


@app.route("/api/personalities", methods=["POST"])
@login_required
def create_personality():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    system_prompt = data.get("system_prompt", "").strip()
    if not name or not system_prompt:
        return jsonify({"error": "Name and personality prompt are required."}), 400
    try:
        with get_db() as conn:
            cur = conn.execute("INSERT INTO personalities (name,system_prompt,base_model) VALUES (?,?,?)",
                               (name, system_prompt, BASE_MODEL))
            conn.commit()
            row = conn.execute("SELECT id,name,system_prompt,base_model FROM personalities WHERE id=?",
                               (cur.lastrowid,)).fetchone()
        return jsonify({"status": "created", "personality": dict(row)})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A personality with that name already exists."}), 409


@app.route("/api/personalities/<int:personality_id>", methods=["GET"])
@login_required
def get_personality(personality_id):
    with get_db() as conn:
        row = conn.execute("SELECT id,name,system_prompt,base_model FROM personalities WHERE id=?",
                           (personality_id,)).fetchone()
    if not row:
        return jsonify({"error": "Personality not found."}), 404
    return jsonify({"personality": dict(row)})


@app.route("/api/personalities/<int:personality_id>", methods=["PUT"])
@login_required
def update_personality(personality_id):
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    system_prompt = data.get("system_prompt", "").strip()
    if not name or not system_prompt:
        return jsonify({"error": "Name and personality prompt are required."}), 400
    try:
        with get_db() as conn:
            if not conn.execute("SELECT id FROM personalities WHERE id=?", (personality_id,)).fetchone():
                return jsonify({"error": "Personality not found."}), 404
            conn.execute("UPDATE personalities SET name=?,system_prompt=?,base_model=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (name, system_prompt, BASE_MODEL, personality_id))
            conn.commit()
            row = conn.execute("SELECT id,name,system_prompt,base_model FROM personalities WHERE id=?",
                               (personality_id,)).fetchone()
        return jsonify({"status": "updated", "personality": dict(row)})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A personality with that name already exists."}), 409


@app.route("/api/personalities/<int:personality_id>", methods=["DELETE"])
@login_required
def delete_personality(personality_id):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM personalities WHERE id=?", (personality_id,)).fetchone():
            return jsonify({"error": "Personality not found."}), 404
        conn.execute("DELETE FROM personalities WHERE id=?", (personality_id,))
        conn.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(force=True)
    personality_id = data.get("personality_id")
    messages = data.get("messages", [])[-6:]

    system_prompt = None
    if personality_id:
        with get_db() as conn:
            persona = conn.execute("SELECT system_prompt FROM personalities WHERE id=?",
                                   (personality_id,)).fetchone()
        if not persona:
            return jsonify({"error": "Personality not found."}), 404
        system_prompt = persona["system_prompt"]

    ollama_messages = list(messages)
    if system_prompt:
        ollama_messages.insert(0, {"role": "system", "content": system_prompt})

    try:
        res = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": BASE_MODEL, "messages": ollama_messages, "stream": True},
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
    print(f"   Ollama host: {OLLAMA_HOST}\n")
    app.run(host="0.0.0.0", port=5000, debug=False)



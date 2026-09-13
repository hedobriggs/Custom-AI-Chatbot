# 💬 Chat Studio

**Created by Hedobriggs 😉**

A local AI chatbot built with Flask, Ollama and Llama 3.2.

## Architecture

Browser → Flask (Docker) → Ollama (Mac) → Llama 3.2

## Features

- Local AI chat
- Streaming responses
- Stop generation
- Persistent chat history
- Custom personalities
- Create, edit and delete personalities
- Light and dark mode
- SQLite storage
- Password-protected access

## Personalities

Personalities are stored in SQLite.

Each personality contains:

- Name
- System prompt
- Base model

Personalities do not create separate Ollama models.

## Setup

1. Make sure Ollama is running.
2. Make sure `llama3.2` is installed.
3. Create your `.env` file.
4. Start the application:

```bash
docker compose up --build -d

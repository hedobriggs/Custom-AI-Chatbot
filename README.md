# NnamdiGpt - Containerized Local AI Frontend Application

An engineered, containerized Python/Flask interface overlay built custom for the local **Llama 3.2** model engine. Includes a secure runtime entry panel and client-side system configuration capabilities.

## 🏗️ Technical Architecture
1. **Ollama Engine (Mac OS Host Layer):** Operates on native hardware using Metal GPU acceleration to host model processing with zero latency.
2. **NnamdiGpt Web Application (Docker Container Layer):** Sandboxed Flask server handling UI presentation and application authentication.
3. **Hardware Gateway Bridge:** Routes user instructions back to the host hardware through custom routing mapping headers via `host.docker.internal:11434`.

---

## 🛠️ Execution & Deployment Guide

### Local Initialisation
1. Pull your model dependency on your Mac host machine:
   ```bash
   ollama pull llama3.2
   ```
2. Build and orchestrate the local system suite container infrastructure:
   ```bash
   docker compose up --build -d
   ```
3. Load the access gateway path in your browser: `http://localhost:5000`
4. Enter systemic credentials to enter the interface dashboard:
   * **Authentication Key:** `NnamdiGpt`

---

## ☁️ Cloud Infrastructure Mapping (AWS EC2)
To host NnamdiGpt on AWS:
1. **Host Selection:** Build a **`g4dn.xlarge`** or **`g5`** compute node instance running Ubuntu Server or Amazon Linux 2023.
2. **Security Firewall Groups:** Configure entry filtering settings to allow secure access mapping rules:
   * **Inbound Protocol:** TCP | **Port:** 22 | **Scope:** Admin Management IP
   * **Inbound Protocol:** TCP | **Port:** 5000 | **Scope:** Public (0.0.0.0/0)
3. **Execution Routing:** Pull down this reference repository codebase from GitHub onto the EC2 host node, install standard Docker binaries, and execute `docker compose up -d`.


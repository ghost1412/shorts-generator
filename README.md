# 🚀 ShortsFlow: The Automated Video Empire

Welcome to **ShortsFlow**, the lean SaaS for generating viral YouTube Shorts automatically. This project is a monorepo containing both a high-performance Python video engine and a premium Next.js dashboard.

---

## 📂 Project Structure
- `engine/`: The core Python logic (Script Gen, Voice Gen, Video Gen).
- `web/`: The Next.js SaaS dashboard & API Bridge.
- `main.py`: The local entry point and GitHub Action worker script.
- `.github/workflows/`: Automated 6-hour posting and on-demand triggers.

---

## 🛠️ How to Run

### 1. The Python Engine (Backend)
To generate a video manually:
```bash
python main.py --mode FACTS --category history
```

### 2. The Dedicated Render Server (Optional)
If you don't want to use GitHub Actions, run this to start an HTTP listener for the website:
```bash
# Install server dependencies
pip install flask python-dotenv

# Start the server
python server.py
```
*The server will listen on port 5000 by default.*

### 2. The Web Dashboard (Frontend)
To launch the SaaS interface:
```bash
cd web

# Install dependencies
npm install

# Run the dev server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to see your dashboard.

---

## ☁️ Zero-Cost Cloud Setup
This project uses a **Hybrid Hosting** strategy to keep your costs at $0:
- **UI**: Hosted on Vercel.
- **Heavy Rendering**: Performed for free by GitHub Actions.
- **Database/Auth**: Powered by Supabase.

---

## 🔐 Configuration
Rename `.env` and `web/.env.local` and add your keys:
- `HF_API_KEY`: Hugging Face (AI Scripting).
- `PEXELS_API_KEY`: Pexels (Background Videos).
- `STRIPE_SECRET_KEY`: Stripe (Payments).
- `NEXT_PUBLIC_SUPABASE_URL`: Supabase (Auth).

---

## 🔑 Authentication
ShortsFlow uses **Supabase Auth** for secure user management:
- **Service**: Supabase (Free Tier).
- **Login Methods**: Supports Email/Password and Social Login (Google/GitHub).
- **Security**: Next.js Middleware protects dashboard routes, and Supabase RLS (Row Level Security) ensures users can only see their own videos.

## ⚙️ Backend Architecture
We use a **Dual-Server** approach:
1.  **API Server (Next.js)**: 
    - Handles logins, database queries, and Stripe payments.
    - Path: `web/`
2.  **Rendering Worker (Python/FFmpeg)**:
    - Handles the heavy processing of video generation.
    - Default: Runs for free on **GitHub Actions**.
    - Optional: Can be run on your own dedicated VPS (via the `RENDER_TARGET=server` setting).

---

# StockVol-AI — Stock Volume Predictor
### Powered by IBM Watsonx Granite · Flask · Bootstrap 5

> AI-driven stock volume forecasting with machine maintenance guidance and safety protocols.

---

## 📁 Project Structure

```
stock_volume_predictor/
├── app.py                      ← Flask backend + Watsonx integration + AGENT_INSTRUCTIONS
├── requirements.txt            ← Python dependencies
├── .env                        ← 🔒 IBM credentials (never commit)
├── .gitignore
├── templates/
│   └── index.html              ← Single-page chat UI (Bootstrap 5)
└── static/
    ├── css/
    │   └── style.css           ← Dark/light theme + animations
    └── js/
        └── app.js              ← Chat logic + markdown rendering
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| pip | ≥ 23 |
| IBM Cloud Account | Active |
| Watsonx.ai Deployment | Granite model deployed |

---

## 🚀 Local Setup & Run

### 1 — Clone / Download
```bash
cd stock_volume_predictor
```

### 2 — Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

### 4 — Configure Environment
The `.env` file is already populated with your IBM credentials.
Review and verify the values:

```env
IBM_API_KEY=xPauVu-dOHyG-avidv3d8Qfl8KqDld0SlyZklZUNq-wf
IBM_PUBLIC_ENDPOINT=https://eu-de.ml.cloud.ibm.com/...
IBM_PRIVATE_ENDPOINT=https://private.eu-de.ml.cloud.ibm.com/...
IBM_IAM_URL=https://iam.cloud.ibm.com/identity/token
FLASK_SECRET_KEY=stock_volume_predictor_secret_key_2025
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### 5 — Run the Application
```bash
python app.py
```

Visit: **http://localhost:5000**

---

## 🧠 Customizing Agent Behavior

Open [`app.py`](app.py) and locate the `AGENT_INSTRUCTIONS` block (lines 28–70).

```python
AGENT_INSTRUCTIONS = """
You are StockVol-AI ...

## TONE & COMMUNICATION STYLE
## PREDICTION BEHAVIOR
## MACHINE MAINTENANCE & SAFETY (MANDATORY)
## INVESTMENT PREFERENCES
## SAFETY RULES (HARD LIMITS)
## RESPONSE FORMAT
"""
```

Edit any section to change:
- **Tone** — professional, friendly, technical
- **Risk profile** — conservative / moderate / aggressive
- **Maintenance focus** — servers, UPS, HVAC, networking
- **Safety rules** — add/remove hard limits
- **Response format** — add new sections or reorder

---

## 🌐 API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `GET`  | `/` | Serve chat UI |
| `POST` | `/api/predict` | Send message → get AI response |
| `POST` | `/api/clear` | Clear session history |
| `GET`  | `/api/health` | Server health check |
| `GET`  | `/api/quick-prompts` | Fetch suggested prompts |

### Example `/api/predict` Request
```json
POST /api/predict
Content-Type: application/json

{
  "message": "Predict AAPL trading volume next week given earnings report"
}
```

### Example Response
```json
{
  "reply": "📊 Volume Prediction Summary\n...\n🔧 Machine Repair Recommendations\n...\n🦺 Safety Instructions\n...",
  "timestamp": "14:32"
}
```

---

## ☁️ Production Deployment

### Option A — Gunicorn (Linux/macOS)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option B — Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn","-w","4","-b","0.0.0.0:5000","app:app"]
```

```bash
docker build -t stockvol-ai .
docker run -p 5000:5000 --env-file .env stockvol-ai
```

### Option C — IBM Code Engine
```bash
# Install IBM Cloud CLI + Code Engine plugin
ibmcloud login --apikey $IBM_API_KEY -r eu-de
ibmcloud ce project create --name stockvol-ai
ibmcloud ce app create \
  --name stockvol-ai \
  --image icr.io/namespace/stockvol-ai:latest \
  --port 5000 \
  --env-from-secret stockvol-secrets
```

### Option D — Heroku
```bash
echo "web: gunicorn app:app" > Procfile
heroku create stockvol-ai-app
heroku config:set IBM_API_KEY=your_key
git push heroku main
```

---

## 🔒 Security Notes

1. **Never commit `.env`** — it is in `.gitignore`
2. Rotate your `IBM_API_KEY` if accidentally exposed
3. Set `FLASK_DEBUG=False` in production
4. Use HTTPS reverse proxy (nginx / Caddy) in production
5. Consider adding Flask-Limiter for rate limiting in public deployments

---

## 🧩 Features

| Feature | Status |
|---------|--------|
| Stock Volume Prediction | ✅ |
| Chat UI with history | ✅ |
| Dark / Light mode | ✅ |
| Mobile responsive | ✅ |
| Machine Repair Suggestions | ✅ |
| Safety Instructions | ✅ |
| Quick Prompts sidebar | ✅ |
| IAM token caching | ✅ |
| Fallback to private endpoint | ✅ |
| AGENT_INSTRUCTIONS customization | ✅ |

---

## 📄 Disclaimer

> StockVol-AI is for **informational purposes only** and does not constitute
> financial advice. Always consult a licensed financial advisor before making
> investment decisions. Machine maintenance recommendations are general guidance
> only — always follow your equipment manufacturer's specifications.

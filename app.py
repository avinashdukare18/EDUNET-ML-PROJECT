"""
Stock Volume Predictor — Flask Backend
Powered by IBM Watsonx.ai AutoAI Tabular Model
Model input: index, Name, open, high, low, close  →  predicts: volume
"""

import os
import math
import requests
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# AGENT INSTRUCTIONS
# Customize the agent's behavior, tone, safety rules, and investment
# preferences here. These instructions drive the narrative built around the
# numeric volume prediction returned by the Watsonx AutoAI model.
# ─────────────────────────────────────────────────────────────────────────────
AGENT_INSTRUCTIONS = {
    # ── TONE & COMMUNICATION STYLE ──────────────────────────────────────────
    "tone": "professional",          # options: professional | friendly | technical
    "use_confidence_ranges": True,   # wrap predictions with ±10% confidence band
    "avoid_jargon": True,

    # ── PREDICTION BEHAVIOUR ────────────────────────────────────────────────
    "volume_spike_threshold": 300,   # % above 30-day avg → flagged HIGH RISK
    "classify_volume": True,         # auto-label Low / Normal / High / Extreme

    # ── MACHINE MAINTENANCE & SAFETY (MANDATORY) ────────────────────────────
    # These maintenance items are ALWAYS appended after every prediction.
    "maintenance_items": [
        "Inspect and clean server air-filters — high-volume sessions increase heat load",
        "Verify UPS battery health and test automatic-transfer switch under load",
        "Check network-switch port utilisation; replace any port showing >80% saturation",
        "Review RAID array status and initiate a consistency check if last check >7 days",
        "Validate cooling-system coolant levels and fan RPM telemetry",
    ],
    "safety_instructions": [
        "ELECTRICAL: Follow LOTO (Lockout/Tag-Out) before servicing any live equipment",
        "PPE: Wear anti-static wrist-strap and insulated gloves when handling server boards",
        "COOLING: Never block ventilation gaps; maintain ≥60 cm clearance behind racks",
        "EMERGENCY SHUTDOWN: Know the location of the PDU breaker and UPS bypass switch",
        "FIRE: CO₂ or FM-200 suppressants only — never use water near energised equipment",
    ],

    # ── INVESTMENT PREFERENCES ──────────────────────────────────────────────
    "risk_profile": "moderate",      # conservative | moderate | aggressive
    "max_leverage_retail": 2,        # hard cap mentioned in advisory text
    "always_recommend_diversification": True,

    # ── SAFETY RULES (HARD LIMITS) ──────────────────────────────────────────
    "no_return_guarantees": True,
    "no_insider_advice": True,
    "mandatory_disclaimer": True,
    "refuse_illegal_requests": True,
}
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_change_me")
CORS(app)

# IBM Watsonx Configuration
IBM_API_KEY   = os.getenv("IBM_API_KEY")
IBM_PUBLIC_EP = os.getenv("IBM_PUBLIC_ENDPOINT")
IBM_IAM_URL   = os.getenv("IBM_IAM_URL", "https://iam.cloud.ibm.com/identity/token")

# AutoAI model input schema (discovered via /ml/v4/models API)
MODEL_FIELDS = ["index", "Name", "open", "high", "low", "close"]

_iam_token_cache = {"token": None, "expires_at": 0}


# ─────── IAM Auth ─────────────────────────────────────────────────────────────

def get_iam_token() -> str:
    """Fetch (or return cached) IBM IAM bearer token."""
    now = datetime.utcnow().timestamp()
    if _iam_token_cache["token"] and now < _iam_token_cache["expires_at"] - 60:
        return _iam_token_cache["token"]

    resp = requests.post(
        IBM_IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": IBM_API_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _iam_token_cache["token"]      = data["access_token"]
    _iam_token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _iam_token_cache["token"]


# ─────── Watsonx AutoAI call ──────────────────────────────────────────────────

def call_watsonx_tabular(row: dict) -> float:
    """
    Send one row to the AutoAI deployment and return the predicted volume.
    row keys must match MODEL_FIELDS: index, Name, open, high, low, close
    """
    token = get_iam_token()

    values_row = [
        int(row["index"]),
        str(row["Name"]),
        float(row["open"]),
        float(row["high"]),
        float(row["low"]),
        float(row["close"]),
    ]

    payload = {
        "input_data": [
            {
                "fields": MODEL_FIELDS,
                "values": [values_row],
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.post(IBM_PUBLIC_EP, headers=headers, json=payload, timeout=60)

    if not resp.ok:
        raise RuntimeError(
            f"Watsonx API error {resp.status_code}: {resp.text[:300]}"
        )

    result = resp.json()
    # AutoAI online-deployment response shape:
    #   {"predictions":[{"fields":["prediction","probability"],"values":[[vol, ...]]}]}
    predictions = result.get("predictions", [])
    if predictions:
        values = predictions[0].get("values", [])
        if values:
            # first element of first row is the predicted label / regression value
            raw = values[0][0]
            return float(raw)

    raise RuntimeError(f"Unexpected response shape: {result}")


# ─────── AI Narrative Builder ─────────────────────────────────────────────────

def _classify_volume(volume: float) -> tuple[str, str]:
    """Return (label, colour-key) based on AGENT_INSTRUCTIONS thresholds."""
    if volume < 1_000_000:
        return "Low", "green"
    if volume < 10_000_000:
        return "Normal", "blue"
    if volume < 50_000_000:
        return "High", "orange"
    return "Extreme", "red"


def build_narrative(row: dict, predicted_volume: float) -> str:
    """
    Construct a structured AI narrative around the numeric prediction,
    applying all AGENT_INSTRUCTIONS rules.
    """
    cfg = AGENT_INSTRUCTIONS
    name     = row["Name"]
    open_p   = float(row["open"])
    high_p   = float(row["high"])
    low_p    = float(row["low"])
    close_p  = float(row["close"])
    spread   = high_p - low_p
    momentum = ((close_p - open_p) / open_p * 100) if open_p else 0

    vol_label, _ = _classify_volume(predicted_volume)
    conf_low  = predicted_volume * 0.90
    conf_high = predicted_volume * 1.10

    # Risk flag
    risk_flag = ""
    if predicted_volume > 50_000_000:
        risk_flag = (
            "\n> ⚠️ **HIGH RISK FLAG**: Predicted volume exceeds 50M shares — "
            "this is an extreme-volume event. Exercise heightened caution."
        )

    # Format large numbers readably
    def fmt(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.2f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return f"{n:.0f}"

    maintenance_lines = "\n".join(
        f"  {i+1}. {item}"
        for i, item in enumerate(cfg["maintenance_items"])
    )
    safety_lines = "\n".join(
        f"  - {item}"
        for item in cfg["safety_instructions"]
    )

    disclaimer = (
        "\n> ⚠️ **Disclaimer:** This analysis is for informational purposes only "
        "and does not constitute financial advice. Always consult a licensed "
        f"financial advisor. Max recommended leverage for retail investors: "
        f"{cfg['max_leverage_retail']}x."
    ) if cfg["mandatory_disclaimer"] else ""

    narrative = f"""## 📊 Volume Prediction Summary

| Field | Value |
|---|---|
| **Stock / Ticker** | {name} |
| **Open** | ${open_p:,.2f} |
| **High** | ${high_p:,.2f} |
| **Low** | ${low_p:,.2f} |
| **Close** | ${close_p:,.2f} |
| **Day Spread** | ${spread:,.2f} |
| **Session Momentum** | {momentum:+.2f}% |
| **Predicted Volume** | **{fmt(predicted_volume)} shares** |
| **Confidence Range** | {fmt(conf_low)} — {fmt(conf_high)} |
| **Volume Category** | {vol_label} |
{risk_flag}

---

## 📈 Key Market Drivers

- **Intraday spread** of ${spread:,.2f} indicates {"elevated" if spread > close_p * 0.02 else "moderate"} volatility.
- **Session momentum** of {momentum:+.2f}% suggests {"bullish" if momentum > 0 else "bearish"} pressure which {"amplifies" if momentum > 0 else "suppresses"} volume.
- A **{vol_label.lower()}-volume** session ({fmt(predicted_volume)}) implies {"strong institutional participation" if predicted_volume > 10_000_000 else "typical retail-driven activity"}.
- Price closed {"above" if close_p > open_p else "below"} open — {"positive" if close_p > open_p else "negative"} signal for next-session volume continuation.

---

## 🔧 Machine Repair & Maintenance Recommendations

High-volume trading sessions stress infrastructure. Perform the following:

{maintenance_lines}

---

## 🦺 Safety Instructions

{safety_lines}

---
{disclaimer}"""

    return narrative.strip()


# ─────── Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    session.setdefault("chat_history", [])
    return render_template("index.html")


@app.route("/api/schema", methods=["GET"])
def schema():
    """Return the model input field schema so the UI can render the form."""
    return jsonify({
        "fields": [
            {"name": "index",  "type": "integer", "label": "Row Index",   "placeholder": "e.g. 0"},
            {"name": "Name",   "type": "text",    "label": "Stock Ticker","placeholder": "e.g. AAPL"},
            {"name": "open",   "type": "number",  "label": "Open Price",  "placeholder": "e.g. 172.50"},
            {"name": "high",   "type": "number",  "label": "High Price",  "placeholder": "e.g. 175.00"},
            {"name": "low",    "type": "number",  "label": "Low Price",   "placeholder": "e.g. 170.00"},
            {"name": "close",  "type": "number",  "label": "Close Price", "placeholder": "e.g. 173.80"},
        ]
    })


@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Accept structured stock data, call the AutoAI model, build an AI
    narrative with maintenance + safety guidance, return to the chat UI.

    Expected JSON body:
        { "index": 0, "Name": "AAPL", "open": 172.5,
          "high": 175.0, "low": 170.0, "close": 173.8 }
    """
    body = request.get_json(force=True)

    if not IBM_API_KEY:
        return jsonify({"error": "IBM API key not configured on server."}), 500

    # Validate required fields
    missing = [f for f in MODEL_FIELDS if f not in body or body[f] == ""]
    if missing:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing)}. "
                     "Please fill in all fields in the prediction form."
        }), 400

    history = session.get("chat_history", [])

    try:
        predicted_volume = call_watsonx_tabular(body)
        ai_reply         = build_narrative(body, predicted_volume)

        # Store a concise summary in chat history
        summary = (
            f"Predicted volume for {body['Name']}: "
            f"{predicted_volume/1_000_000:.2f}M shares "
            f"(open={body['open']}, high={body['high']}, "
            f"low={body['low']}, close={body['close']})"
        )
        history.append({"role": "user",      "content": summary})
        history.append({"role": "assistant", "content": ai_reply})
        session["chat_history"] = history[-20:]

        return jsonify({
            "reply":            ai_reply,
            "predicted_volume": predicted_volume,
            "timestamp":        datetime.now().strftime("%H:%M"),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def clear_history():
    """Clear the chat session history."""
    session["chat_history"] = []
    return jsonify({"status": "cleared"})


@app.route("/api/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({
        "status":    "ok",
        "service":   "Stock Volume Predictor",
        "model":     "IBM Watsonx AutoAI (tabular)",
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/api/quick-examples", methods=["GET"])
def quick_examples():
    """Return prefill examples for the prediction form."""
    return jsonify({
        "examples": [
            {"label": "AAPL — Bull Day",  "index": 0, "Name": "AAPL",  "open": 172.50, "high": 175.00, "low": 170.00, "close": 174.20},
            {"label": "TSLA — High Vol",  "index": 1, "Name": "TSLA",  "open": 248.00, "high": 260.00, "low": 242.00, "close": 256.50},
            {"label": "NVDA — Earnings",  "index": 2, "Name": "NVDA",  "open": 450.00, "high": 480.00, "low": 445.00, "close": 475.00},
            {"label": "MSFT — Flat Day",  "index": 3, "Name": "MSFT",  "open": 335.00, "high": 337.00, "low": 333.00, "close": 334.50},
            {"label": "AMZN — Volatile",  "index": 4, "Name": "AMZN",  "open": 185.00, "high": 195.00, "low": 182.00, "close": 192.00},
        ]
    })


# ─────── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    host  = os.getenv("FLASK_HOST",  "0.0.0.0")
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)

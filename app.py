# -*- coding: utf-8 -*-
"""
Stock Volume Predictor - Flask Backend
Powered by IBM Watsonx.ai AutoAI Tabular Model
Model input: index, Name, open, high, low, close -> predicts: volume
"""

import os
import requests
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# =============================================================================
# AGENT INSTRUCTIONS
# Customize agent behavior, tone, safety rules, and investment preferences.
# =============================================================================
AGENT_INSTRUCTIONS = {
    "tone": "professional",
    "use_confidence_ranges": True,
    "volume_spike_threshold": 300,
    "classify_volume": True,
    "maintenance_items": [
        "Inspect and clean server air-filters - high-volume sessions increase heat load",
        "Verify UPS battery health and test automatic-transfer switch under load",
        "Check network-switch port utilisation; replace any port showing >80% saturation",
        "Review RAID array status and run a consistency check if last check was >7 days ago",
        "Validate cooling-system coolant levels and fan RPM telemetry",
    ],
    "safety_instructions": [
        "ELECTRICAL: Follow LOTO (Lockout/Tag-Out) before servicing any live equipment",
        "PPE: Wear anti-static wrist-strap and insulated gloves when handling server boards",
        "COOLING: Never block ventilation gaps; maintain at least 60 cm clearance behind racks",
        "EMERGENCY SHUTDOWN: Know the location of the PDU breaker and UPS bypass switch",
        "FIRE: Use CO2 or FM-200 suppressants only - never use water near energised equipment",
    ],
    "risk_profile": "moderate",
    "max_leverage_retail": 2,
    "mandatory_disclaimer": True,
}
# =============================================================================

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "stockvol_default_secret_2025")

IBM_API_KEY   = os.getenv("IBM_API_KEY")
IBM_PUBLIC_EP = os.getenv("IBM_PUBLIC_ENDPOINT")
IBM_IAM_URL   = os.getenv("IBM_IAM_URL", "https://iam.cloud.ibm.com/identity/token")
MODEL_FIELDS  = ["index", "Name", "open", "high", "low", "close"]

_iam_token_cache = {"token": None, "expires_at": 0}


# --- IAM Auth -----------------------------------------------------------------

def get_iam_token():
    now = datetime.utcnow().timestamp()
    if _iam_token_cache["token"] and now < _iam_token_cache["expires_at"] - 60:
        return _iam_token_cache["token"]
    resp = requests.post(
        IBM_IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": IBM_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _iam_token_cache["token"]      = data["access_token"]
    _iam_token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _iam_token_cache["token"]


# --- Watsonx AutoAI -----------------------------------------------------------

def call_watsonx_tabular(row):
    token = get_iam_token()
    payload = {
        "input_data": [{
            "fields": MODEL_FIELDS,
            "values": [[int(row["index"]), str(row["Name"]),
                        float(row["open"]), float(row["high"]),
                        float(row["low"]),  float(row["close"])]],
        }]
    }
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(IBM_PUBLIC_EP, headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise RuntimeError("Watsonx error " + str(resp.status_code) + ": " + resp.text[:200])
    result = resp.json()
    preds = result.get("predictions", [])
    if preds:
        vals = preds[0].get("values", [])
        if vals:
            return float(vals[0][0])
    raise RuntimeError("Unexpected response: " + str(result)[:200])


# --- Narrative ----------------------------------------------------------------

def fmt_vol(n):
    if n >= 1000000:
        return "{:.2f}M".format(n / 1000000)
    if n >= 1000:
        return "{:.1f}K".format(n / 1000)
    return "{:.0f}".format(n)


def classify_vol(v):
    if v < 1000000:  return "Low"
    if v < 10000000: return "Normal"
    if v < 50000000: return "High"
    return "Extreme"


def build_narrative(row, vol):
    cfg      = AGENT_INSTRUCTIONS
    name     = str(row["Name"])
    op       = float(row["open"])
    hi       = float(row["high"])
    lo       = float(row["low"])
    cl       = float(row["close"])
    spread   = hi - lo
    momentum = ((cl - op) / op * 100) if op else 0
    label    = classify_vol(vol)
    cl_low   = vol * 0.90
    cl_high  = vol * 1.10

    risk = ""
    if vol > 50000000:
        risk = "\n[!] HIGH RISK: Volume exceeds 50M shares - extreme event, exercise caution.\n"

    maint = "\n".join("  {}. {}".format(i+1, x) for i, x in enumerate(cfg["maintenance_items"]))
    safe  = "\n".join("  - {}".format(x) for x in cfg["safety_instructions"])
    disc  = ("\n[DISCLAIMER] Informational only - not financial advice. "
             "Consult a licensed advisor. Max retail leverage: {}x.".format(cfg["max_leverage_retail"]))

    return (
        "## [CHART] Volume Prediction Summary\n\n"
        "| Field | Value |\n|---|---|\n"
        "| Stock | {} |\n"
        "| Open | ${:.2f} |\n"
        "| High | ${:.2f} |\n"
        "| Low  | ${:.2f} |\n"
        "| Close | ${:.2f} |\n"
        "| Spread | ${:.2f} |\n"
        "| Momentum | {:+.2f}% |\n"
        "| **Predicted Volume** | **{} shares** |\n"
        "| Confidence Range | {} to {} |\n"
        "| Category | {} |\n"
        "{}\n\n---\n\n"
        "## [UP] Key Market Drivers\n\n"
        "- Spread of ${:.2f} indicates {} volatility.\n"
        "- Momentum {:+.2f}% suggests {} pressure, which {} volume.\n"
        "- {} volume ({}) implies {}.\n"
        "- Closed {} open - {} signal for next session.\n\n---\n\n"
        "## [WRENCH] Machine Repair and Maintenance\n\n"
        "High-volume sessions stress infrastructure. Act on:\n\n{}\n\n---\n\n"
        "## [SAFETY] Safety Instructions\n\n{}\n\n---\n{}"
    ).format(
        name, op, hi, lo, cl, spread, momentum,
        fmt_vol(vol), fmt_vol(cl_low), fmt_vol(cl_high), label, risk,
        spread, "elevated" if spread > cl * 0.02 else "moderate",
        momentum, "bullish" if momentum > 0 else "bearish",
        "amplifies" if momentum > 0 else "suppresses",
        label, fmt_vol(vol),
        "strong institutional participation" if vol > 10000000 else "typical retail activity",
        "above" if cl > op else "below",
        "positive" if cl > op else "negative",
        maint, safe, disc,
    ).strip()


# --- Routes -------------------------------------------------------------------

@app.route("/")
def index():
    session.setdefault("chat_history", [])
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Stock Volume Predictor",
                    "timestamp": datetime.utcnow().isoformat()})


@app.route("/api/quick-examples", methods=["GET"])
def quick_examples():
    return jsonify({"examples": [
        {"label": "AAPL - Bull Day",  "index": 0, "Name": "AAPL", "open": 172.50, "high": 175.00, "low": 170.00, "close": 174.20},
        {"label": "TSLA - High Vol",  "index": 1, "Name": "TSLA", "open": 248.00, "high": 260.00, "low": 242.00, "close": 256.50},
        {"label": "NVDA - Earnings",  "index": 2, "Name": "NVDA", "open": 450.00, "high": 480.00, "low": 445.00, "close": 475.00},
        {"label": "MSFT - Flat Day",  "index": 3, "Name": "MSFT", "open": 335.00, "high": 337.00, "low": 333.00, "close": 334.50},
        {"label": "AMZN - Volatile",  "index": 4, "Name": "AMZN", "open": 185.00, "high": 195.00, "low": 182.00, "close": 192.00},
    ]})


@app.route("/api/predict", methods=["POST"])
def predict():
    body = request.get_json(force=True)
    if not IBM_API_KEY:
        return jsonify({"error": "IBM API key not configured."}), 500
    missing = [f for f in MODEL_FIELDS if f not in body or str(body[f]).strip() == ""]
    if missing:
        return jsonify({"error": "Missing fields: " + ", ".join(missing)}), 400
    history = session.get("chat_history", [])
    try:
        vol      = call_watsonx_tabular(body)
        ai_reply = build_narrative(body, vol)
        summary  = "Predicted {:.2f}M shares for {}".format(vol / 1000000, body["Name"])
        history.append({"role": "user",      "content": summary})
        history.append({"role": "assistant", "content": ai_reply})
        session["chat_history"] = history[-20:]
        return jsonify({"reply": ai_reply, "predicted_volume": vol,
                        "timestamp": datetime.now().strftime("%H:%M")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def clear_history():
    session["chat_history"] = []
    return jsonify({"status": "cleared"})


# --- Entry Point --------------------------------------------------------------

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)

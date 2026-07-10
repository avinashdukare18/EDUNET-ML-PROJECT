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
# Customize the agent behavior, tone, safety rules, and investment preferences.
# These settings drive the narrative built around the numeric volume prediction.
# =============================================================================
AGENT_INSTRUCTIONS = {
    # -- TONE & COMMUNICATION STYLE -------------------------------------------
    "tone": "professional",         # professional | friendly | technical
    "use_confidence_ranges": True,  # wrap predictions with +/-10% confidence band
    "avoid_jargon": True,

    # -- PREDICTION BEHAVIOUR -------------------------------------------------
    "volume_spike_threshold": 300,  # % above 30-day avg -> flagged HIGH RISK
    "classify_volume": True,        # auto-label Low / Normal / High / Extreme

    # -- MACHINE MAINTENANCE & SAFETY (MANDATORY) -----------------------------
    # These items are ALWAYS appended after every prediction.
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

    # -- INVESTMENT PREFERENCES -----------------------------------------------
    "risk_profile": "moderate",     # conservative | moderate | aggressive
    "max_leverage_retail": 2,       # hard cap mentioned in advisory text
    "always_recommend_diversification": True,

    # -- SAFETY RULES (HARD LIMITS) -------------------------------------------
    "no_return_guarantees": True,
    "no_insider_advice": True,
    "mandatory_disclaimer": True,
    "refuse_illegal_requests": True,
}
# =============================================================================

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_change_me")

# IBM Watsonx Configuration
IBM_API_KEY   = os.getenv("IBM_API_KEY")
IBM_PUBLIC_EP = os.getenv("IBM_PUBLIC_ENDPOINT")
IBM_IAM_URL   = os.getenv("IBM_IAM_URL", "https://iam.cloud.ibm.com/identity/token")

# AutoAI model input schema
MODEL_FIELDS = ["index", "Name", "open", "high", "low", "close"]

_iam_token_cache = {"token": None, "expires_at": 0}


# --- IAM Auth -----------------------------------------------------------------

def get_iam_token():
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


# --- Watsonx AutoAI call ------------------------------------------------------

def call_watsonx_tabular(row):
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
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.post(IBM_PUBLIC_EP, headers=headers, json=payload, timeout=60)

    if not resp.ok:
        raise RuntimeError(
            "Watsonx API error " + str(resp.status_code) + ": " + resp.text[:300]
        )

    result = resp.json()
    predictions = result.get("predictions", [])
    if predictions:
        values = predictions[0].get("values", [])
        if values:
            return float(values[0][0])

    raise RuntimeError("Unexpected response shape: " + str(result))


# --- Volume classifier --------------------------------------------------------

def classify_volume(volume):
    if volume < 1000000:
        return "Low"
    if volume < 10000000:
        return "Normal"
    if volume < 50000000:
        return "High"
    return "Extreme"


def fmt_volume(n):
    if n >= 1000000:
        return "{:.2f}M".format(n / 1000000)
    if n >= 1000:
        return "{:.1f}K".format(n / 1000)
    return "{:.0f}".format(n)


# --- AI Narrative Builder -----------------------------------------------------

def build_narrative(row, predicted_volume):
    cfg       = AGENT_INSTRUCTIONS
    name      = str(row["Name"])
    open_p    = float(row["open"])
    high_p    = float(row["high"])
    low_p     = float(row["low"])
    close_p   = float(row["close"])
    spread    = high_p - low_p
    momentum  = ((close_p - open_p) / open_p * 100) if open_p else 0

    vol_label = classify_volume(predicted_volume)
    conf_low  = predicted_volume * 0.90
    conf_high = predicted_volume * 1.10

    risk_flag = ""
    if predicted_volume > 50000000:
        risk_flag = (
            "\n[!] HIGH RISK FLAG: Predicted volume exceeds 50M shares - "
            "this is an extreme-volume event. Exercise heightened caution.\n"
        )

    maintenance_lines = "\n".join(
        "  {}. {}".format(i + 1, item)
        for i, item in enumerate(cfg["maintenance_items"])
    )
    safety_lines = "\n".join(
        "  - {}".format(item)
        for item in cfg["safety_instructions"]
    )

    disclaimer = (
        "\n[DISCLAIMER] This analysis is for informational purposes only "
        "and does not constitute financial advice. Always consult a licensed "
        "financial advisor. Max recommended leverage for retail investors: {}x.".format(
            cfg["max_leverage_retail"]
        )
    ) if cfg["mandatory_disclaimer"] else ""

    narrative = (
        "## [CHART] Volume Prediction Summary\n\n"
        "| Field | Value |\n"
        "|---|---|\n"
        "| Stock / Ticker | {} |\n"
        "| Open | ${:.2f} |\n"
        "| High | ${:.2f} |\n"
        "| Low | ${:.2f} |\n"
        "| Close | ${:.2f} |\n"
        "| Day Spread | ${:.2f} |\n"
        "| Session Momentum | {:+.2f}% |\n"
        "| Predicted Volume | **{} shares** |\n"
        "| Confidence Range | {} -- {} |\n"
        "| Volume Category | {} |\n"
        "{}\n\n"
        "---\n\n"
        "## [UP] Key Market Drivers\n\n"
        "- Intraday spread of ${:.2f} indicates {} volatility.\n"
        "- Session momentum of {:+.2f}% suggests {} pressure which {} volume.\n"
        "- A {}-volume session ({}) implies {}.\n"
        "- Price closed {} open - {} signal for next-session volume continuation.\n\n"
        "---\n\n"
        "## [WRENCH] Machine Repair and Maintenance Recommendations\n\n"
        "High-volume trading sessions stress infrastructure. Perform the following:\n\n"
        "{}\n\n"
        "---\n\n"
        "## [SAFETY] Safety Instructions\n\n"
        "{}\n\n"
        "---\n"
        "{}"
    ).format(
        name,
        open_p, high_p, low_p, close_p,
        spread,
        momentum,
        fmt_volume(predicted_volume),
        fmt_volume(conf_low), fmt_volume(conf_high),
        vol_label,
        risk_flag,
        spread,
        "elevated" if spread > close_p * 0.02 else "moderate",
        momentum,
        "bullish" if momentum > 0 else "bearish",
        "amplifies" if momentum > 0 else "suppresses",
        vol_label.lower(),
        fmt_volume(predicted_volume),
        "strong institutional participation" if predicted_volume > 10000000 else "typical retail-driven activity",
        "above" if close_p > open_p else "below",
        "positive" if close_p > open_p else "negative",
        maintenance_lines,
        safety_lines,
        disclaimer,
    )

    return narrative.strip()


# --- Routes -------------------------------------------------------------------

@app.route("/")
def index():
    session.setdefault("chat_history", [])
    return render_template("index.html")


@app.route("/api/schema", methods=["GET"])
def schema():
    return jsonify({
        "fields": [
            {"name": "index",  "type": "integer", "label": "Row Index",    "placeholder": "e.g. 0"},
            {"name": "Name",   "type": "text",    "label": "Stock Ticker", "placeholder": "e.g. AAPL"},
            {"name": "open",   "type": "number",  "label": "Open Price",   "placeholder": "e.g. 172.50"},
            {"name": "high",   "type": "number",  "label": "High Price",   "placeholder": "e.g. 175.00"},
            {"name": "low",    "type": "number",  "label": "Low Price",    "placeholder": "e.g. 170.00"},
            {"name": "close",  "type": "number",  "label": "Close Price",  "placeholder": "e.g. 173.80"},
        ]
    })


@app.route("/api/predict", methods=["POST"])
def predict():
    body = request.get_json(force=True)

    if not IBM_API_KEY:
        return jsonify({"error": "IBM API key not configured on server."}), 500

    missing = [f for f in MODEL_FIELDS if f not in body or str(body[f]).strip() == ""]
    if missing:
        return jsonify({
            "error": "Missing required fields: {}. Please fill in all fields.".format(
                ", ".join(missing)
            )
        }), 400

    history = session.get("chat_history", [])

    try:
        predicted_volume = call_watsonx_tabular(body)
        ai_reply         = build_narrative(body, predicted_volume)

        summary = "Predicted volume for {}: {:.2f}M shares (open={}, high={}, low={}, close={})".format(
            body["Name"],
            predicted_volume / 1000000,
            body["open"], body["high"], body["low"], body["close"],
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
    session["chat_history"] = []
    return jsonify({"status": "cleared"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "ok",
        "service":   "Stock Volume Predictor",
        "model":     "IBM Watsonx AutoAI (tabular)",
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/api/quick-examples", methods=["GET"])
def quick_examples():
    return jsonify({
        "examples": [
            {"label": "AAPL - Bull Day",  "index": 0, "Name": "AAPL", "open": 172.50, "high": 175.00, "low": 170.00, "close": 174.20},
            {"label": "TSLA - High Vol",  "index": 1, "Name": "TSLA", "open": 248.00, "high": 260.00, "low": 242.00, "close": 256.50},
            {"label": "NVDA - Earnings",  "index": 2, "Name": "NVDA", "open": 450.00, "high": 480.00, "low": 445.00, "close": 475.00},
            {"label": "MSFT - Flat Day",  "index": 3, "Name": "MSFT", "open": 335.00, "high": 337.00, "low": 333.00, "close": 334.50},
            {"label": "AMZN - Volatile",  "index": 4, "Name": "AMZN", "open": 185.00, "high": 195.00, "low": 182.00, "close": 192.00},
        ]
    })


# --- Entry Point --------------------------------------------------------------

if __name__ == "__main__":
    host  = os.getenv("FLASK_HOST",  "0.0.0.0")
    port  = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)

/**
 * StockVol-AI  ·  Frontend
 * IBM Watsonx AutoAI Tabular Model — structured OHLC input → volume prediction
 */
"use strict";

/* ── DOM refs ── */
const chatMessages    = document.getElementById("chatMessages");
const predictionForm  = document.getElementById("predictionForm");
const predictBtn      = document.getElementById("predictBtn");
const predictIcon     = document.getElementById("predictIcon");
const predictLabel    = document.getElementById("predictLabel");
const typingIndicator = document.getElementById("typingIndicator");
const statusDot       = document.getElementById("statusDot");
const statusLabel     = document.getElementById("statusLabel");
const themeToggle     = document.getElementById("themeToggle");
const themeIcon       = document.getElementById("themeIcon");
const clearBtn        = document.getElementById("clearBtn");
const exampleBtns     = document.getElementById("exampleBtns");
const volBadge        = document.getElementById("volBadge");

let isSending = false;

/* ── Theme ── */
function getTheme() { return localStorage.getItem("stockvol-theme") || "dark"; }
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("stockvol-theme", t);
  themeIcon.className = t === "dark" ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
}
themeToggle.addEventListener("click", () => applyTheme(getTheme() === "dark" ? "light" : "dark"));
applyTheme(getTheme());

/* ── Health check ── */
async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    if (r.ok) {
      statusDot.className    = "status-dot online";
      statusLabel.textContent = "Online";
    } else throw new Error();
  } catch {
    statusDot.className    = "status-dot error";
    statusLabel.textContent = "Offline";
  }
}
checkHealth();

/* ── Load quick-fill examples ── */
async function loadExamples() {
  try {
    const r    = await fetch("/api/quick-examples");
    const data = await r.json();
    exampleBtns.innerHTML = "";
    (data.examples || []).forEach(ex => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      btn.textContent = ex.label;
      btn.addEventListener("click", () => fillForm(ex));
      exampleBtns.appendChild(btn);
    });
  } catch {
    exampleBtns.innerHTML = '<span style="font-size:0.75rem;color:var(--text-dim)">Could not load examples</span>';
  }
}
loadExamples();

/* ── Fill form from example ── */
function fillForm(ex) {
  document.getElementById("f_index").value = ex.index ?? 0;
  document.getElementById("f_name").value  = ex.Name  ?? "";
  document.getElementById("f_open").value  = ex.open  ?? "";
  document.getElementById("f_high").value  = ex.high  ?? "";
  document.getElementById("f_low").value   = ex.low   ?? "";
  document.getElementById("f_close").value = ex.close ?? "";
  // clear validation state
  predictionForm.querySelectorAll(".inp").forEach(i => i.classList.remove("is-invalid"));
}

/* ── Welcome card ── */
function renderWelcome() {
  chatMessages.innerHTML = `
    <div class="welcome-card animate-fade-in">
      <i class="bi bi-graph-up-arrow welcome-icon"></i>
      <h4>Ready to predict</h4>
      <p>Fill in the OHLC stock data on the left and click <strong>Predict Volume</strong>.<br>
         The IBM Watsonx AutoAI model will return a volume forecast along with<br>
         machine maintenance tips and safety instructions.</p>
      <div class="suggestion-chips">
        <span class="chip" id="sc1">📊 Try AAPL</span>
        <span class="chip" id="sc2">⚡ Try TSLA</span>
        <span class="chip" id="sc3">🔥 Try NVDA</span>
      </div>
    </div>`;

  // wire suggestion chips to quick-fill once examples are loaded
  document.getElementById("sc1").addEventListener("click", () => fillFormByLabel("AAPL — Bull Day"));
  document.getElementById("sc2").addEventListener("click", () => fillFormByLabel("TSLA — High Vol"));
  document.getElementById("sc3").addEventListener("click", () => fillFormByLabel("NVDA — Earnings"));
}

async function fillFormByLabel(label) {
  const r    = await fetch("/api/quick-examples");
  const data = await r.json();
  const ex   = (data.examples || []).find(e => e.label === label);
  if (ex) fillForm(ex);
}

renderWelcome();

/* ── Markdown-lite renderer ── */
function escHtml(t) {
  return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function mdToHtml(raw) {
  let s = escHtml(raw);

  // Tables  (pipe-delimited)
  s = s.replace(/\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/g, (_, head, body) => {
    const ths = head.split("|").filter(c => c.trim()).map(c => `<th>${c.trim()}</th>`).join("");
    const rows = body.trim().split("\n").map(row => {
      const tds = row.split("|").filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join("");
      return `<tr>${tds}</tr>`;
    }).join("");
    return `<div class="table-wrap"><table class="ai-table"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
  });

  // Headers
  s = s.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  s = s.replace(/^## (.+)$/gm,  "<h2>$1</h2>");

  // Blockquote
  s = s.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // Bold + italic
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.+?)\*/g,     "<em>$1</em>");

  // Inline code
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");

  // HR
  s = s.replace(/^---$/gm, "<hr />");

  // Bullets
  s = s.replace(/((?:^[ ]*[-*] .+\n?)+)/gm, m => {
    const items = m.trim().split("\n").map(l => `<li>${l.replace(/^[ ]*[-*] /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });

  // Numbered list
  s = s.replace(/((?:^[ ]*\d+\. .+\n?)+)/gm, m => {
    const items = m.trim().split("\n").map(l => `<li>${l.replace(/^\d+\. /, "")}</li>`).join("");
    return `<ol>${items}</ol>`;
  });

  // Paragraphs
  s = s.replace(/\n\n+/g, "</p><p>");
  s = s.replace(/\n/g, "<br />");

  return `<p>${s}</p>`;
}

/* ── Append a message bubble ── */
function appendMessage(role, htmlContent, ts, isError = false) {
  const wc = chatMessages.querySelector(".welcome-card");
  if (wc) wc.remove();

  const wrap = document.createElement("div");
  wrap.className = `message ${role === "user" ? "user-msg" : "bot-msg"}`;

  const avatar =
    role === "user"
      ? `<div class="ai-avatar user-av"><i class="bi bi-bar-chart-fill"></i></div>`
      : `<div class="ai-avatar-sm bot-av"><i class="bi bi-robot"></i></div>`;

  wrap.innerHTML = `
    ${avatar}
    <div style="max-width:100%;overflow:hidden">
      <div class="msg-bubble ${isError ? "error-bubble" : ""}">${htmlContent}</div>
      <div class="msg-time">${ts || now()}</div>
    </div>`;

  chatMessages.appendChild(wrap);
  scrollToBottom();
}

function now() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function scrollToBottom() {
  chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: "smooth" });
}

/* ── Update the volume badge in the chat header ── */
function updateVolBadge(vol) {
  if (!vol) return;
  const m = vol / 1_000_000;
  let cls = "badge-normal";
  if (vol >= 50_000_000) cls = "badge-extreme";
  else if (vol >= 10_000_000) cls = "badge-high";
  else if (vol < 1_000_000) cls = "badge-low";
  volBadge.className  = `vol-badge ${cls}`;
  volBadge.textContent = `${m.toFixed(2)}M shares`;
  volBadge.classList.remove("d-none");
}

/* ── Form submission → prediction ── */
predictionForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (isSending) return;

  // Validate
  const inputs = predictionForm.querySelectorAll("[required]");
  let valid = true;
  inputs.forEach(inp => {
    if (!inp.value.trim()) {
      inp.classList.add("is-invalid");
      valid = false;
    } else {
      inp.classList.remove("is-invalid");
    }
  });
  if (!valid) return;

  const payload = {
    index: parseInt(document.getElementById("f_index").value),
    Name:  document.getElementById("f_name").value.trim().toUpperCase(),
    open:  parseFloat(document.getElementById("f_open").value),
    high:  parseFloat(document.getElementById("f_high").value),
    low:   parseFloat(document.getElementById("f_low").value),
    close: parseFloat(document.getElementById("f_close").value),
  };

  // Sanity check: high >= open/close >= low
  if (payload.high < payload.open || payload.high < payload.close ||
      payload.low  > payload.open || payload.low  > payload.close) {
    appendMessage("bot",
      `<strong>⚠️ Invalid OHLC data:</strong> High must be ≥ Open &amp; Close; Low must be ≤ Open &amp; Close.`,
      now(), true);
    return;
  }

  isSending = true;
  predictBtn.disabled = true;
  predictIcon.className = "";
  predictBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Predicting…';

  // Show user summary bubble
  appendMessage("user", `
    <strong>📥 Prediction Request</strong><br/>
    <span class="tag">${payload.Name}</span>
    &nbsp;Open <code>$${payload.open}</code>
    · High <code>$${payload.high}</code>
    · Low <code>$${payload.low}</code>
    · Close <code>$${payload.close}</code>`, now());

  typingIndicator.classList.remove("d-none");
  scrollToBottom();

  try {
    const resp = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    typingIndicator.classList.add("d-none");

    if (!resp.ok || data.error) {
      appendMessage("bot", `<strong>⚠️ Error:</strong> ${escHtml(data.error || "Unexpected error")}`,
        now(), true);
    } else {
      appendMessage("bot", mdToHtml(data.reply), data.timestamp || now());
      updateVolBadge(data.predicted_volume);
    }
  } catch (err) {
    typingIndicator.classList.add("d-none");
    appendMessage("bot", `<strong>⚠️ Network error:</strong> ${escHtml(err.message)}`, now(), true);
  } finally {
    isSending = false;
    predictBtn.disabled = false;
    predictBtn.innerHTML = '<i class="bi bi-lightning-charge-fill me-2" id="predictIcon"></i><span>Predict Volume</span>';
  }
});

/* ── Clear chat ── */
clearBtn.addEventListener("click", async () => {
  if (!confirm("Clear prediction history?")) return;
  await fetch("/api/clear", { method: "POST" });
  volBadge.classList.add("d-none");
  renderWelcome();
});

/* ── Inline validation on blur ── */
predictionForm.querySelectorAll(".inp").forEach(inp => {
  inp.addEventListener("blur", () => {
    if (inp.hasAttribute("required") && !inp.value.trim()) {
      inp.classList.add("is-invalid");
    } else {
      inp.classList.remove("is-invalid");
    }
  });
});

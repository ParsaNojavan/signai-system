#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const char *WIFI_SSID = "";
const char *WIFI_PASS = "";

// ==========================================
// 1.OLED
// ==========================================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_SDA 8
#define OLED_SCL 9
#define OLED_ADDR 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ==========================================
// 2. OV2640 (S3 + PSRAM)
// ==========================================
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 10
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 15

#define Y9_GPIO_NUM 48
#define Y8_GPIO_NUM 11
#define Y7_GPIO_NUM 12
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 16
#define Y4_GPIO_NUM 17
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 21

#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 13

WebServer server(80);

// ==========================================
// 3. Auth (HTML+CSS+JS)
// ==========================================
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>سامانه هوشمند تشخیص زبان اشاره</title>
  <style>
    :root {
      --bg-color: #09090b;
      --card-bg: rgba(24, 24, 27, 0.75);
      --border-color: rgba(39, 39, 42, 0.8);
      --accent: #10b981;
      --accent-hover: #059669;
      --danger: #ef4444;
      --text-main: #f4f4f5;
      --text-muted: #a1a1aa;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
    body { background: var(--bg-color); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 16px; position: relative; }
    
    .bg-grid { position: fixed; inset: 0; background-image: linear-gradient(to right, rgba(39,39,42,0.15) 1px, transparent 1px), linear-gradient(to bottom, rgba(39,39,42,0.15) 1px, transparent 1px); background-size: 4rem 4rem; mask-image: radial-gradient(ellipse 60% 50% at 50% 50%, #000 70%, transparent 100%); pointer-events: none; z-index: 0; }
    
    .view-card { position: relative; z-index: 1; width: 100%; max-width: 400px; background: rgba(24, 24, 27, 0.65); border: 1px solid var(--border-color); border-radius: 16px; padding: 24px; backdrop-filter: blur(16px); box-shadow: 0 20px 30px -10px rgba(0,0,0,0.6); }
    .dashboard-container { display: none; width: 100%; max-width: 860px; z-index: 1; flex-direction: column; gap: 16px; margin: auto; }
    
    .icon-box { width: 42px; height: 42px; border-radius: 10px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); display: flex; align-items: center; justify-content: center; color: var(--accent); margin: 0 auto 12px auto; }
    h2 { font-size: 19px; font-weight: 600; text-align: center; }
    p.subtitle { font-size: 12px; color: var(--text-muted); text-align: center; margin-top: 4px; margin-bottom: 20px; }
    
    .alert { padding: 10px 14px; border-radius: 8px; font-size: 12px; margin-bottom: 14px; display: none; align-items: center; gap: 8px; }
    .alert-err { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.25); color: #f87171; }
    .alert-ok { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); color: #6ee7b7; }
    
    .tab-switch { display: grid; grid-template-columns: 1fr 1fr; background: #09090b; padding: 4px; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 18px; }
    .tab-btn { background: transparent; border: none; color: var(--text-muted); padding: 6px; font-size: 12px; font-weight: 500; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
    .tab-btn.active { background: #27272a; color: #fff; }
    
    .form-group { margin-bottom: 14px; text-align: right; }
    .form-group label { display: block; font-size: 12px; color: #d4d4d8; margin-bottom: 6px; }
    .input-wrap { position: relative; }
    .input-wrap input { width: 100%; height: 38px; background: rgba(9, 9, 11, 0.6); border: 1px solid var(--border-color); border-radius: 8px; color: #fff; font-size: 13px; padding: 0 12px; outline: none; transition: border 0.2s; }
    .input-wrap input:focus { border-color: var(--accent); }
    .otp-input { text-align: center; letter-spacing: 0.5em; font-family: monospace; font-size: 18px; font-weight: bold; }
    
    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: 100%; height: 38px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: all 0.2s; text-decoration: none; }
    .btn-primary { background: #059669; color: #fff; }
    .btn-primary:hover { background: #047857; }
    .btn-danger { background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.3); color: #f87171; }
    .btn-danger:hover { background: rgba(239, 68, 68, 0.25); }
    .btn-sub { background: transparent; color: var(--text-muted); font-size: 12px; margin-top: 10px; border: none; }
    .btn-sub:hover { color: #fff; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; }
    .brand { display: flex; align-items: center; gap: 10px; }
    .badge { display: flex; align-items: center; gap: 6px; font-size: 11px; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border-color); background: #18181b; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #71717a; }
    .status-dot.connected { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
    .status-dot.error { background: var(--danger); box-shadow: 0 0 8px var(--danger); }
    
    .card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 16px; backdrop-filter: blur(12px); box-shadow: 0 10px 25px -5px rgba(0,0,0,0.4); }
    .video-container { position: relative; width: 100%; aspect-ratio: 4/3; background: #000; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border-color); }
    img#preview { width: 100%; height: 100%; object-fit: contain; }
    
    .controls { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-top: 12px; }
    .btn-group { display: flex; gap: 8px; flex-wrap: wrap; width: auto; }
    .btn-group .btn { width: auto; padding: 0 16px; }

    .transcribed-output { min-height: 80px; background: rgba(0,0,0,0.6); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px; font-family: monospace; font-size: 20px; color: #6ee7b7; word-break: break-all; display: flex; align-items: center; direction: ltr; text-align: left; }
    .placeholder { font-family: system-ui; font-size: 13px; color: var(--text-muted); direction: rtl; }
  </style>
</head>
<body>

  <div class="bg-grid"></div>

  <!-- 1. پنل ورود و ثبت‌نام -->
  <div class="view-card" id="authSection">
    <div class="icon-box">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
    </div>
    <h2>سیستم ترجمه زبان اشاره</h2>
    <p class="subtitle" id="authSubtitle">ورود یا عضویت در سامانه هوشمند</p>

    <div class="alert alert-err" id="authErr"></div>
    <div class="alert alert-ok" id="authOk"></div>

    <div class="tab-switch">
      <button class="tab-btn active" id="tabLogin" onclick="switchAuthTab('login')">ورود</button>
      <button class="tab-btn" id="tabRegister" onclick="switchAuthTab('register')">ثبت‌نام</button>
    </div>

    <form id="formLogin" onsubmit="handleLogin(event)">
      <div class="form-group">
        <label>نام کاربری یا ایمیل</label>
        <div class="input-wrap"><input type="text" id="loginId" placeholder="username یا user@mail.com" required></div>
      </div>
      <div class="form-group">
        <label>رمز عبور</label>
        <div class="input-wrap"><input type="password" id="loginPass" placeholder="••••••••" required></div>
      </div>
      <button type="submit" class="btn btn-primary" id="btnLogin">ورود به حساب</button>
    </form>

    <form id="formRegister" style="display:none;" onsubmit="handleRegister(event)">
      <div class="form-group">
        <label>نام کاربری</label>
        <div class="input-wrap"><input type="text" id="regUser" placeholder="مثال: parsa" required></div>
      </div>
      <div class="form-group">
        <label>آدرس ایمیل</label>
        <div class="input-wrap"><input type="email" id="regEmail" placeholder="example@mail.com" required></div>
      </div>
      <div class="form-group">
        <label>رمز عبور</label>
        <div class="input-wrap"><input type="password" id="regPass" placeholder="حداقل ۶ کاراکتر" required></div>
      </div>
      <button type="submit" class="btn btn-primary" id="btnRegister">ثبت‌نام و دریافت کد تأیید</button>
    </form>
  </div>

  <!-- 2. پنل تأیید دو مرحله‌ای ایمیل (Verify) -->
  <div class="view-card" id="verifySection" style="display:none;">
    <div class="icon-box">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
    </div>
    <h2>تأیید حساب کاربری</h2>
    <p class="subtitle">کد ۶ رقمی ارسال‌شده به ایمیلتان را وارد کنید</p>

    <div class="alert alert-err" id="verifyErr"></div>

    <form onsubmit="handleVerify(event)">
      <div class="form-group">
        <label>ایمیل مقصد</label>
        <div class="input-wrap"><input type="email" id="verifyEmail" readonly style="color:var(--text-muted);"></div>
      </div>
      <div class="form-group">
        <label>کد ۶ رقمی</label>
        <div class="input-wrap"><input type="text" id="verifyCode" class="otp-input" maxlength="6" placeholder="••••••" required autofocus></div>
      </div>
      <button type="submit" class="btn btn-primary" id="btnVerify">تأیید و فعال‌سازی اکانت</button>
      <button type="button" class="btn btn-sub" onclick="backToAuth()">بازگشت به صفحه ورود</button>
    </form>
  </div>

  <!-- 3. داشبورد اصلی -->
  <div class="dashboard-container" id="dashboardSection">
    <header>
      <div class="brand">
        <div class="icon-box" style="margin:0; width:34px; height:34px;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="m8 17 4 4 4-4"></path></svg>
        </div>
        <div>
          <h2 style="font-size:15px; text-align:right;">داشبورد استنتاج زنده SignAI</h2>
          <span style="font-size:11px; color:var(--text-muted);" id="userDisplay">کاربر: احراز شده</span>
        </div>
      </div>
      
      <div style="display:flex; align-items:center; gap:8px;">
        <div class="badge">
          <span class="status-dot" id="wsDot"></span>
          <span id="wsStatusText">سوکت قطع</span>
        </div>
        <button class="btn btn-danger" style="width:auto; height:30px; padding:0 12px; font-size:11px;" onclick="handleLogout()">خروج</button>
      </div>
    </header>

    <div class="card">
      <div class="video-container">
        <img id="preview" src="/capture" alt="Inference Feed">
      </div>
      
      <div class="controls">
        <div class="btn-group">
          <button id="btnStart" class="btn btn-primary" onclick="startInferenceLoop()">شروع ارسال به مدل</button>
          <button id="btnStop" class="btn btn-danger" onclick="stopInferenceLoop()" disabled>توقف</button>
          <select id="modeSelect" style="background:#09090b; border:1px solid var(--border-color); color:#fff; border-radius:8px; padding:0 8px; font-size:12px;">
            <option value="talking">حالت کلمات (Talking)</option>
            <option value="spelling">حالت حروف (Spelling)</option>
          </select>
        </div>
        
        <div style="font-size:12px; font-family:monospace; color:var(--text-muted); display:flex; gap:12px;">
          <span>FPS: <b id="fpsVal" style="color:#fff;">0</b></span>
          <span>دست: <b id="handVal" style="color:#fff;">---</b></span>
          <span>بافر: <b id="bufVal" style="color:#fff;">--</b></span>
        </div>
      </div>
    </div>

    <div class="card" style="display:flex; flex-direction:column; gap:10px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:13px; color:var(--text-muted);">خروجی استخراج شده:</span>
        <div class="btn-group">
          <button class="btn" style="width:auto; height:30px; padding:0 12px; background:#18181b; border:1px solid var(--border-color); color:#fff;" onclick="addSpace()">Space</button>
          <button class="btn" style="width:auto; height:30px; padding:0 12px; background:#18181b; border:1px solid var(--border-color); color:#fff;" onclick="removeLastChar()">حذف</button>
          <button class="btn btn-danger" style="width:auto; height:30px; padding:0 12px;" onclick="clearText()">پاکسازی</button>
          <button class="btn btn-primary" style="width:auto; height:30px; padding:0 12px;" onclick="copyText()">کپی</button>
        </div>
      </div>
      
      <div class="transcribed-output" id="outputBox">
        <span class="placeholder">کلمات یا کاراکترهای ترجمه‌شده اینجا درج می‌شوند...</span>
      </div>
    </div>
  </div>

  <script>
    const API_BASE_URL = "http://192.168.1.107:8000";
    const WS_BASE_URL  = "ws://192.168.1.107:8000/ws/inference";

    let token = localStorage.getItem("signai_token") || null;
    let ws = null;
    let loopActive = false;
    let captureInProgress = false;
    let timerId = null;
    let frameCounter = 0;
    let lastFpsTime = performance.now();

    const authSection      = document.getElementById("authSection");
    const verifySection    = document.getElementById("verifySection");
    const dashboardSection = document.getElementById("dashboardSection");

    const authErr   = document.getElementById("authErr");
    const authOk    = document.getElementById("authOk");
    const verifyErr = document.getElementById("verifyErr");

    window.addEventListener("DOMContentLoaded", () => {
      if (token) {
        showDashboard();
      } else {
        showAuth();
      }
    });

    function showAuth() {
      authSection.style.display = "block";
      verifySection.style.display = "none";
      dashboardSection.style.display = "none";
      document.body.style.justifyContent = "center";
    }

    function showVerify(email) {
      authSection.style.display = "none";
      verifySection.style.display = "block";
      dashboardSection.style.display = "none";
      document.getElementById("verifyEmail").value = email;
      document.getElementById("verifyCode").focus();
    }

    function showDashboard() {
      authSection.style.display = "none";
      verifySection.style.display = "none";
      dashboardSection.style.display = "flex";
      document.body.style.justifyContent = "flex-start";
    }

    function switchAuthTab(type) {
      authErr.style.display = "none";
      authOk.style.display = "none";
      if (type === "login") {
        document.getElementById("tabLogin").className = "tab-btn active";
        document.getElementById("tabRegister").className = "tab-btn";
        document.getElementById("formLogin").style.display = "block";
        document.getElementById("formRegister").style.display = "none";
      } else {
        document.getElementById("tabLogin").className = "tab-btn";
        document.getElementById("tabRegister").className = "tab-btn active";
        document.getElementById("formLogin").style.display = "none";
        document.getElementById("formRegister").style.display = "block";
      }
    }

    function backToAuth() {
      showAuth();
      switchAuthTab("login");
    }

    async function handleLogin(e) {
      e.preventDefault();
      authErr.style.display = "none";
      const btn = document.getElementById("btnLogin");
      btn.disabled = true;
      btn.innerText = "در حال ورود...";

      const id = document.getElementById("loginId").value.trim();
      const password = document.getElementById("loginPass").value;

      try {
        const res = await fetch(`${API_BASE_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username_or_email: id, password })
        });
        const data = await res.json();
        
        if (!res.ok) {
          if (data.detail && data.detail.includes("تأیید")) {
            showVerify(id.includes("@") ? id : "");
            return;
          }
          throw new Error(data.detail || "اطلاعات ورود اشتباه است");
        }

        token = data.access_token;
        localStorage.setItem("signai_token", token);
        showDashboard();
      } catch (err) {
        authErr.innerText = err.message;
        authErr.style.display = "flex";
      } finally {
        btn.disabled = false;
        btn.innerText = "ورود به حساب";
      }
    }

    async function handleRegister(e) {
      e.preventDefault();
      authErr.style.display = "none";
      const btn = document.getElementById("btnRegister");
      btn.disabled = true;
      btn.innerText = "در حال ارسال کد...";

      const username = document.getElementById("regUser").value.trim();
      const email = document.getElementById("regEmail").value.trim().toLowerCase();
      const password = document.getElementById("regPass").value;

      try {
        const res = await fetch(`${API_BASE_URL}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "خطا در ثبت نام");

        showVerify(email);
      } catch (err) {
        authErr.innerText = err.message;
        authErr.style.display = "flex";
      } finally {
        btn.disabled = false;
        btn.innerText = "ثبت‌نام و دریافت کد تأیید";
      }
    }

    async function handleVerify(e) {
      e.preventDefault();
      verifyErr.style.display = "none";
      const btn = document.getElementById("btnVerify");
      btn.disabled = true;
      btn.innerText = "در حال احراز...";

      const email = document.getElementById("verifyEmail").value;
      const code = document.getElementById("verifyCode").value.trim();

      try {
        const res = await fetch(`${API_BASE_URL}/auth/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, code })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "کد تأیید نادرست یا منقضی است");

        if (data.access_token) {
          token = data.access_token;
          localStorage.setItem("signai_token", token);
          showDashboard();
        } else {
          backToAuth();
          authOk.innerText = "ایمیل شما تأیید شد. اکنون وارد شوید.";
          authOk.style.display = "flex";
        }
      } catch (err) {
        verifyErr.innerText = err.message;
        verifyErr.style.display = "flex";
      } finally {
        btn.disabled = false;
        btn.innerText = "تأیید و فعال‌سازی اکانت";
      }
    }

    function handleLogout() {
      stopInferenceLoop();
      localStorage.removeItem("signai_token");
      token = null;
      showAuth();
      switchAuthTab("login");
    }

    const wsDot = document.getElementById("wsDot");
    const wsStatusText = document.getElementById("wsStatusText");
    const preview = document.getElementById("preview");
    const outputBox = document.getElementById("outputBox");
    const modeSelect = document.getElementById("modeSelect");

    function setWsState(state, text) {
      wsDot.className = "status-dot " + (state === "ok" ? "connected" : state === "err" ? "error" : "");
      wsStatusText.innerText = text;
    }

    function startInferenceLoop() {
      if (!token) {
        handleLogout();
        return;
      }
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

      const mode = modeSelect.value;
      const wsUrl = `${WS_BASE_URL}?token=${encodeURIComponent(token)}&mode=${encodeURIComponent(mode)}`;

      setWsState("wait", "در حال اتصال...");
      ws = new WebSocket(wsUrl);
      ws.binaryType = "blob";

      ws.onopen = () => {
        setWsState("ok", `متصل (${mode})`);
        document.getElementById("btnStart").disabled = true;
        document.getElementById("btnStop").disabled = false;
        loopActive = true;
        tickStream();
      };

      ws.onmessage = (event) => {
        try {
          const res = JSON.parse(event.data);
          if (res.hand_mode) document.getElementById("handVal").innerText = res.hand_mode;
          
          if (res.action === "buffering") {
            document.getElementById("bufVal").innerText = `${res.frames_collected}/${res.frames_required}`;
            return;
          } else {
            document.getElementById("bufVal").innerText = "آماده";
          }

          if (res.action && !["idle", "buffering", "uncertain", "invalid_frame"].includes(res.action.trim())) {
            appendChar(res.action);
          }
        } catch (e) {
          if (typeof event.data === "string" && event.data.length > 0) appendChar(event.data);
        }
      };

      ws.onerror = (err) => {
        setWsState("err", "خطا در احراز سوکت");
      };

      ws.onclose = (ev) => {
        setWsState("err", "سوکت قطع شد");
        stopInferenceLoop();
        if (ev.code === 1008 || ev.code === 4001) {
          alert("اعتبار توکن تمام شده است. لطفاً مجدداً وارد شوید.");
          handleLogout();
        }
      };
    }

    async function tickStream() {
      if (!loopActive) return;

      if (!captureInProgress && ws && ws.readyState === WebSocket.OPEN) {
        captureInProgress = true;
        try {
          const res = await fetch("/capture?t=" + Date.now(), { cache: "no-store" });
          if (res.ok) {
            const blob = await res.blob();
            preview.src = URL.createObjectURL(blob);
            ws.send(blob);

            frameCounter++;
            const now = performance.now();
            if (now - lastFpsTime >= 1000) {
              document.getElementById("fpsVal").innerText = frameCounter;
              frameCounter = 0;
              lastFpsTime = now;
            }
          }
        } catch (err) {
          console.warn("Frame drop:", err);
        } finally {
          captureInProgress = false;
        }
      }

      if (loopActive) timerId = setTimeout(tickStream, 85);
    }

    function stopInferenceLoop() {
      loopActive = false;
      if (timerId) clearTimeout(timerId);
      if (ws) {
        const old = ws;
        ws = null;
        old.close();
      }
      document.getElementById("btnStart").disabled = false;
      document.getElementById("btnStop").disabled = true;
      document.getElementById("fpsVal").innerText = "0";
      document.getElementById("handVal").innerText = "---";
      document.getElementById("bufVal").innerText = "--";
    }

    function appendChar(val) {
      if (outputBox.querySelector('.placeholder')) outputBox.innerHTML = '';
      outputBox.innerText += (modeSelect.value === "talking" ? " " : "") + val;
    }
    function addSpace() { appendChar(' '); }
    function removeLastChar() {
      if (outputBox.querySelector('.placeholder')) return;
      outputBox.innerText = outputBox.innerText.trimEnd().slice(0, -1);
      if (!outputBox.innerText.length) {
        outputBox.innerHTML = '<span class="placeholder">کلمات یا کاراکترهای ترجمه‌شده اینجا درج می‌شوند...</span>';
      }
    }
    function clearText() {
      outputBox.innerHTML = '<span class="placeholder">کلمات یا کاراکترهای ترجمه‌شده اینجا درج می‌شوند...</span>';
    }
    function copyText() {
      if (outputBox.querySelector('.placeholder')) return;
      navigator.clipboard.writeText(outputBox.innerText);
    }
  </script>
</body>
</html>
)rawliteral";

// ==========================================
// 4. Manage Http roots
// ==========================================
void handleRoot()
{
  server.sendHeader("Connection", "close");
  server.send(200, "text/html", INDEX_HTML);
}

void handleFavicon()
{
  server.sendHeader("Connection", "close");
  server.send(204);
}

void handleCapture()
{
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb)
  {
    server.send(503, "text/plain", "Camera busy");
    return;
  }

  size_t len = fb->len;
  uint8_t *buf = fb->buf;

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Connection", "close");
  server.setContentLength(len);
  server.send(200, "image/jpeg", "");

  WiFiClient client = server.client();
  client.write(buf, len);

  esp_camera_fb_return(fb);
}

// ==========================================
// 5. Camera startup
// ==========================================
bool initCamera()
{
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 8000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 2;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK)
    return false;

  sensor_t *s = esp_camera_sensor_get();
  if (s != NULL)
  {
    s->set_vflip(s, 1);
    s->set_hmirror(s, 0);
  }

  return true;
}

// ==========================================
// 6. Loop & Setup
// ==========================================
void setup()
{
  Serial.begin(115200);
  delay(1000);

  Wire.begin(OLED_SDA, OLED_SCL);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR))
  {
    Serial.println(F("[ERROR] SSD1306 allocation failed"));
  }
  else
  {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println("Booting SignAI...");
    display.display();
  }

  if (!initCamera())
  {
    Serial.println("[ERROR] Camera init failed!");
    display.clearDisplay();
    display.setCursor(0, 10);
    display.println("Cam Init Failed!");
    display.display();
    return;
  }
  Serial.println("[OK] Camera Initialized.");

  display.clearDisplay();
  display.setCursor(0, 10);
  display.println("Camera OK.");
  display.println("Connecting WiFi...");
  display.display();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(400);
    Serial.print(".");
  }

  Serial.printf("\n[WiFi] Connected!\n");
  Serial.printf("[Dashboard URL] http://%s\n", WiFi.localIP().toString().c_str());

  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(0, 5);
  display.println("SignAI");

  display.setTextSize(1);
  display.setCursor(0, 35);
  display.println("Connected!");
  display.setCursor(0, 50);
  display.print("IP: ");
  display.println(WiFi.localIP().toString());
  display.display();

  server.on("/", handleRoot);
  server.on("/favicon.ico", handleFavicon);
  server.on("/capture", handleCapture);

  server.begin();
  Serial.println("[HTTP] Server ready.");
}

void loop()
{
  server.handleClient();
}

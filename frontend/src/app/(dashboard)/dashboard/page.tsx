"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Cookies from "js-cookie";
import { useAuth } from "@/context/AuthContext";
import {
  Camera,
  CameraOff,
  SwitchCamera,
  Layers,
  Sparkles,
  Copy,
  Check,
  Trash2,
  Delete,
  Space,
  Volume2,
  History,
  LogOut,
  Settings2,
} from "lucide-react";

interface DetectionHistoryItem {
  id: string;
  label: string;
  confidence: number;
  time: string;
  mode: "talking" | "spelling";
}

interface ServerResponse {
  action?: string;
  confidence?: number;
  hand_mode?: string;
  frames_collected?: number;
  frames_required?: number;
}

const TARGET_FPS = 12;
const SEND_INTERVAL_MS = Math.round(1000 / TARGET_FPS);
const HOLD_REQUIRED_MS = 450;
const COOLDOWN_SAME_GESTURE_MS = 800;

export default function DashboardPage() {
  const { user, logout } = useAuth();

  const [mode, setMode] = useState<"talking" | "spelling">("talking");
  const [facingMode, setFacingMode] = useState<"user" | "environment">("user");

  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [fps, setFps] = useState(0);

  const [actionStatus, setActionStatus] = useState<string>("---");
  const [statusType, setStatusType] = useState<"idle" | "buffering" | "uncertain" | "detected">("idle");
  const [handMode, setHandMode] = useState<string>("---");
  const [confidence, setConfidence] = useState<number>(0);
  const [holdProgress, setHoldProgress] = useState<number>(0);

  const [transcribedText, setTranscribedText] = useState<string>("");
  const [history, setHistory] = useState<DetectionHistoryItem[]>([]);
  const [copied, setCopied] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sendIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isProcessingRef = useRef<boolean>(false);
  const fpsTrackerRef = useRef<{ count: number; lastTime: number }>({
    count: 0,
    lastTime: performance.now(),
  });

  const stabilityRef = useRef<{
    candidate: string | null;
    firstSeenAt: number;
    lastCommittedAt: number;
    lastCommittedGesture: string | null;
  }>({
    candidate: null,
    firstSeenAt: 0,
    lastCommittedAt: 0,
    lastCommittedGesture: null,
  });

  const stopStream = useCallback((closeSocket = true) => {
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }

    if (closeSocket && wsRef.current) {
      try {
        wsRef.current.close();
      } catch (_) { }
    }
    wsRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    isProcessingRef.current = false;
    stabilityRef.current = {
      candidate: null,
      firstSeenAt: 0,
      lastCommittedAt: 0,
      lastCommittedGesture: null,
    };

    setIsStreaming(false);
    setConnectionStatus("disconnected");
    setFps(0);
    setActionStatus("---");
    setStatusType("idle");
    setConfidence(0);
    setHandMode("---");
    setHoldProgress(0);
  }, []);

  const sendFrame = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (isProcessingRef.current) return;
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video.videoWidth || !video.videoHeight) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    canvas.width = 480;
    canvas.height = 360;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          isProcessingRef.current = true;
          wsRef.current.send(blob);

          fpsTrackerRef.current.count += 1;
          const now = performance.now();
          if (now - fpsTrackerRef.current.lastTime >= 1000) {
            setFps(fpsTrackerRef.current.count);
            fpsTrackerRef.current.count = 0;
            fpsTrackerRef.current.lastTime = now;
          }
        }
      },
      "image/jpeg",
      0.55
    );
  }, []);

  const commitGesture = useCallback((label: string, conf: number, currentMode: "talking" | "spelling") => {
    setTranscribedText((prev) => {
      if (currentMode === "spelling") {
        return prev + label;
      } else {
        const words = prev.trim().split(" ");
        if (words[words.length - 1] === label) return prev;
        return prev ? `${prev} ${label}` : label;
      }
    });

    setHistory((prev) => [
      {
        id: Math.random().toString(36).substring(7),
        label,
        confidence: conf,
        time: new Date().toLocaleTimeString("fa-IR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        mode: currentMode,
      },
      ...prev.slice(0, 24),
    ]);
  }, []);

  const startStream = async (targetFacingMode = facingMode) => {
    stopStream();

    const token = Cookies.get("sign_auth_token");
    if (!token) {
      alert("توکن احراز هویت یافت نشد. لطفاً دوباره وارد حساب شوید.");
      return;
    }

    try {
      setConnectionStatus("connecting");

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: targetFacingMode,
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 24 },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsStreaming(true);

      const baseWsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/inference";
      const urlObj = new URL(baseWsUrl);
      urlObj.searchParams.set("token", token);
      urlObj.searchParams.set("mode", mode);
      const wsUrl = urlObj.toString();

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "blob";
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus("connected");
        sendIntervalRef.current = setInterval(sendFrame, SEND_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        isProcessingRef.current = false;
        let res: ServerResponse;

        try {
          res = JSON.parse(event.data);
        } catch {
          console.error("Invalid WS response:", event.data);
          return;
        }

        setHandMode(res.hand_mode || "---");

        if (res.action === "idle") {
          setActionStatus("در انتظار دست");
          setStatusType("idle");
          setConfidence(0);
          setHoldProgress(0);
          stabilityRef.current.candidate = null;
          return;
        }

        if (res.action === "buffering") {
          setActionStatus(`در حال ثبت (${res.frames_collected ?? 0}/${res.frames_required ?? 0})`);
          setStatusType("buffering");
          setHoldProgress(0);
          return;
        }

        const conf = res.confidence || 0;
        setConfidence(conf);

        if (res.action === "uncertain") {
          setActionStatus("نامطمئن");
          setStatusType("uncertain");
          setHoldProgress(0);
          stabilityRef.current.candidate = null;
          return;
        }

        if (res.action) {
          const detected = String(res.action).toUpperCase();
          setActionStatus(detected);
          setStatusType("detected");

          const now = performance.now();
          const stab = stabilityRef.current;

          if (mode === "talking") {
            setHoldProgress(100);
            commitGesture(detected, conf, "talking");
            return;
          }

          if (stab.candidate !== detected) {
            stab.candidate = detected;
            stab.firstSeenAt = now;
            setHoldProgress(10);
            return;
          }

          const heldTime = now - stab.firstSeenAt;
          const progress = Math.min(100, Math.round((heldTime / HOLD_REQUIRED_MS) * 100));
          setHoldProgress(progress);

          if (heldTime >= HOLD_REQUIRED_MS) {
            const isSameAsLastCommit = stab.lastCommittedGesture === detected;
            const timeSinceLastCommit = now - stab.lastCommittedAt;

            if (!isSameAsLastCommit || timeSinceLastCommit >= COOLDOWN_SAME_GESTURE_MS) {
              commitGesture(detected, conf, "spelling");
              stab.lastCommittedGesture = detected;
              stab.lastCommittedAt = now;
              stab.firstSeenAt = now;
            }
          }
        }
      };

      ws.onclose = (event) => {
        console.warn("WebSocket Closed:", event.code, event.reason);
        stopStream(false);
      };

      ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
        stopStream(false);
      };
    } catch (err: unknown) {
      stopStream(false);
      alert("خطا در ارتباط: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const toggleFacingMode = () => {
    const nextMode = facingMode === "user" ? "environment" : "user";
    setFacingMode(nextMode);
    if (isStreaming) {
      startStream(nextMode);
    }
  };

  const addSpace = () => setTranscribedText((prev) => prev + " ");
  const removeLastChar = () => setTranscribedText((prev) => prev.slice(0, -1));
  const clearAllText = () => setTranscribedText("");

  const copyText = () => {
    if (!transcribedText) return;
    navigator.clipboard.writeText(transcribedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const speakText = () => {
    if (!transcribedText || !("speechSynthesis" in window)) return;
    setIsSpeaking(true);
    const utterance = new SpeechSynthesisUtterance(transcribedText);
    utterance.lang = "en-US";
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, [stopStream]);

  return (
    <div
      dir="rtl"
      className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-400"
    >
      <canvas ref={canvasRef} className="hidden" />

      {/* هدر */}
      <header className="sticky top-0 z-30 w-full border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-md px-3 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 shrink-0">
            <Layers className="h-4 w-4 sm:h-5 sm:w-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <h1 className="text-xs sm:text-sm font-semibold text-zinc-100">SignAI Live System</h1>
              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[10px] text-emerald-400 font-mono">
                Real-time
              </span>
            </div>
            <p className="text-[10px] sm:text-[11px] text-zinc-400 hidden xs:block">
              تشخیص زنده کلمات و الفبای اشاره
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 sm:gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2 sm:px-3 py-1 sm:py-1.5 text-xs text-zinc-300">
            <span className="font-mono text-zinc-400 text-[11px] sm:text-xs">کاربر:</span>
            <span className="font-medium text-zinc-200 max-w-[80px] sm:max-w-[120px] truncate">
              {user?.username || "کاربر"}
            </span>
          </div>

          <button
            onClick={logout}
            title="خروج از حساب"
            className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-red-400 hover:border-red-500/30 transition-colors shrink-0"
          >
            <LogOut className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
          </button>
        </div>
      </header>

      {/* محتوای اصلی */}
      <main className="flex-1 p-3 sm:p-5 lg:p-6 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-5">

        {/* ستون اصلی: وب‌کم و متن */}
        <div className="lg:col-span-8 flex flex-col gap-4 lg:gap-5 order-1">
          {/* کادر وب‌کم */}
          <div className="relative rounded-2xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md overflow-hidden flex flex-col shadow-2xl">
            {/* نوار وضعیت بالای تصویر */}
            <div className="flex items-center justify-between border-b border-zinc-800/80 px-3 sm:px-4 py-2 bg-zinc-900/60 text-xs">
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <span
                    className={`h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full ${connectionStatus === "connected"
                      ? "bg-emerald-400 animate-pulse"
                      : connectionStatus === "connecting"
                        ? "bg-amber-400 animate-ping"
                        : "bg-zinc-600"
                      }`}
                  />
                  <span className="text-zinc-300 font-medium text-[11px] sm:text-xs">
                    {connectionStatus === "connected"
                      ? "متصل به سرور"
                      : connectionStatus === "connecting"
                        ? "در حال اتصال..."
                        : "قطع ارتباط"}
                  </span>
                </div>

                <div className="flex items-center gap-1 font-mono text-[10px] sm:text-[11px] text-zinc-400 border-r border-zinc-800 pr-2 mr-1">
                  <span>hand:</span>
                  <span className="text-emerald-400">{handMode}</span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 font-mono text-[10px] sm:text-[11px]">
                <div className="rounded-md border border-zinc-800 bg-zinc-950 px-2 py-0.5 sm:px-2.5 sm:py-1 text-zinc-300 flex items-center gap-1">
                  <span className="text-zinc-500 text-[9px] sm:text-[10px]">FPS:</span>
                  <span className={fps >= 10 ? "text-emerald-400 font-bold" : "text-zinc-400"}>
                    {fps}
                  </span>
                </div>
              </div>
            </div>

            {/* صفحه استریم ویدیو */}
            <div className="relative aspect-[4/3] sm:aspect-video w-full bg-zinc-950 flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover ${facingMode === "user" ? "-scale-x-100" : ""
                  } ${!isStreaming ? "hidden" : ""}`}
              />

              {!isStreaming && (
                <div className="flex flex-col items-center justify-center gap-2 sm:gap-3 p-6 text-center">
                  <div className="flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/60 text-zinc-500">
                    <CameraOff className="h-5 w-5 sm:h-6 sm:w-6" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs sm:text-sm font-medium text-zinc-300">دوربین متوقف است</p>
                    <p className="text-[11px] sm:text-xs text-zinc-500 max-w-xs">
                      برای شروع روی دکمه شروع استریم کلیک کنید.
                    </p>
                  </div>
                </div>
              )}

              {/* HUD وضعیت روی تصویر */}
              {isStreaming && (
                <div className="absolute top-2.5 left-2.5 sm:top-3 sm:left-3 flex flex-wrap items-center gap-1.5 sm:gap-2 pointer-events-none">
                  <div className="bg-zinc-950/85 backdrop-blur border border-zinc-800 text-[10px] sm:text-[11px] font-mono text-amber-400 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-lg">
                    mode: <span>{mode}</span>
                  </div>

                  {mode === "spelling" && holdProgress > 0 && (
                    <div className="bg-zinc-950/85 backdrop-blur border border-zinc-800 text-[10px] sm:text-[11px] font-mono text-emerald-400 px-2 py-0.5 sm:px-2 sm:py-1 rounded-lg flex items-center gap-1.5">
                      <span>HOLD:</span>
                      <div className="w-10 sm:w-12 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-400 h-1.5 transition-all duration-75"
                          style={{ width: `${holdProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* کنترل‌های پایین ویدیو */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 p-3 sm:p-3.5 bg-zinc-900/80 border-t border-zinc-800/80">
              <div className="flex items-center gap-2">
                {!isStreaming ? (
                  <button
                    onClick={() => startStream()}
                    className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3.5 sm:px-4 py-2 text-xs font-medium text-white hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-950/50"
                  >
                    <Camera className="h-4 w-4 shrink-0" />
                    <span>شروع استریم</span>
                  </button>
                ) : (
                  <button
                    onClick={() => stopStream(true)}
                    className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-2 rounded-lg bg-red-600/90 px-3.5 sm:px-4 py-2 text-xs font-medium text-white hover:bg-red-500 transition-colors shadow-sm"
                  >
                    <CameraOff className="h-4 w-4 shrink-0" />
                    <span>توقف استریم</span>
                  </button>
                )}

                <button
                  onClick={toggleFacingMode}
                  title="سوییچ دوربین"
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-300 hover:text-white transition-colors shrink-0"
                >
                  <SwitchCamera className="h-4 w-4 shrink-0" />
                  <span className="hidden sm:inline">چرخش دوربین</span>
                </button>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Settings2 className="h-4 w-4 text-zinc-400 shrink-0 hidden md:inline" />
                <span className="text-xs text-zinc-400 shrink-0 hidden md:inline">حالت:</span>
                <select
                  value={mode}
                  disabled={isStreaming}
                  onChange={(e) => setMode(e.target.value as "talking" | "spelling")}
                  className="w-full sm:w-auto bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-emerald-500 disabled:opacity-50"
                >
                  <option value="talking">کلمات پیوسته (Talking)</option>
                  <option value="spelling">هجی کردن و الفبا (Spelling)</option>
                </select>
              </div>
            </div>
          </div>

          {/* باکس متن ساخته شده */}
          <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md p-3.5 sm:p-4 flex flex-col gap-3 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                <Sparkles className="h-4 w-4 text-emerald-400 shrink-0" />
                متن نهایی:
              </span>

              {/* ابزارهای نوار متن */}
              <div className="grid grid-cols-5 sm:flex sm:flex-wrap items-center gap-1.5">
                <button
                  onClick={addSpace}
                  title="فاصله (Space)"
                  className="flex items-center justify-center gap-1 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1.5 sm:px-2.5 sm:py-1 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
                >
                  <Space className="h-3.5 w-3.5 shrink-0" />
                  <span className="hidden sm:inline">Space</span>
                </button>

                <button
                  onClick={removeLastChar}
                  title="حذف آخرین حرف"
                  className="flex items-center justify-center gap-1 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1.5 sm:px-2.5 sm:py-1 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
                >
                  <Delete className="h-3.5 w-3.5 shrink-0" />
                  <span className="hidden sm:inline">حذف</span>
                </button>

                <button
                  onClick={clearAllText}
                  title="پاک کردن کامل"
                  className="flex items-center justify-center gap-1 rounded-md border border-red-500/20 bg-red-500/10 px-2 py-1.5 sm:px-2.5 sm:py-1 text-xs text-red-400 hover:bg-red-500/20 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5 shrink-0" />
                  <span className="hidden sm:inline">کل</span>
                </button>

                <button
                  onClick={speakText}
                  title="پخش صوتی"
                  disabled={!transcribedText || isSpeaking}
                  className="flex items-center justify-center gap-1 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1.5 sm:px-2.5 sm:py-1 text-xs text-zinc-300 hover:text-emerald-400 transition-colors disabled:opacity-50"
                >
                  <Volume2 className={`h-3.5 w-3.5 shrink-0 ${isSpeaking ? "animate-bounce" : ""}`} />
                  <span className="hidden sm:inline">تلفظ</span>
                </button>

                <button
                  onClick={copyText}
                  title="کپی متن"
                  className="flex items-center justify-center gap-1 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-1.5 sm:px-2.5 sm:py-1 text-xs text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                >
                  {copied ? <Check className="h-3.5 w-3.5 shrink-0" /> : <Copy className="h-3.5 w-3.5 shrink-0" />}
                  <span className="hidden sm:inline">{copied ? "کپی شد" : "کپی"}</span>
                </button>
              </div>
            </div>

            <div className="min-h-[70px] sm:min-h-[85px] w-full rounded-xl border border-zinc-800 bg-zinc-950/70 p-3 sm:p-4 font-mono text-base sm:text-xl text-emerald-300 tracking-wider flex items-center select-all break-all overflow-y-auto max-h-32 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
              {transcribedText ? (
                transcribedText
              ) : (
                <span className="text-zinc-600 text-xs sm:text-sm font-sans tracking-normal select-none">
                  حروف یا کلمات ثبت‌شده اینجا قرار می‌گیرند...
                </span>
              )}
            </div>
          </div>
        </div>

        {/* سایدبار اطلاعات و تاریخچه */}
        <div className="lg:col-span-4 flex flex-col gap-4 lg:gap-5 order-2">
          {/* کارت‌های وضعیت سرور و اطمینان */}
          <div className="grid grid-cols-2 lg:grid-cols-1 gap-3 sm:gap-4">
            <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-3.5 sm:p-4 shadow-xl flex flex-col justify-between">
              <div className="text-[11px] sm:text-xs text-zinc-400 font-medium truncate">
                {mode === "spelling" ? "نشانه تشخیص داده‌شده" : "کلمه تشخیص داده‌شده"}
              </div>
              <div
                className={`mt-2 truncate tracking-wide ${statusType === "detected"
                  ? "text-2xl sm:text-3xl font-black text-emerald-400"
                  : statusType === "buffering"
                    ? "text-sm sm:text-base font-medium text-amber-400"
                    : statusType === "uncertain"
                      ? "text-base sm:text-xl font-bold text-amber-500"
                      : "text-base sm:text-xl font-bold text-zinc-500"
                  }`}
              >
                {actionStatus}
              </div>
            </div>

            <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-3.5 sm:p-4 shadow-xl flex flex-col justify-between">
              <div className="text-[11px] sm:text-xs text-zinc-400 font-medium flex justify-between items-center">
                <span>اطمینان</span>
                <span className="font-mono text-zinc-300 text-xs">
                  {Math.round(confidence * 100)}%
                </span>
              </div>
              <div className="w-full bg-zinc-950 rounded-full h-2 sm:h-2.5 mt-3 overflow-hidden border border-zinc-800">
                <div
                  className={`h-full rounded-full transition-all duration-150 ${statusType === "uncertain" ? "bg-amber-500" : "bg-emerald-500"
                    }`}
                  style={{ width: `${Math.round(confidence * 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* لیست تاریخچه */}
          <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md p-3.5 sm:p-4 flex flex-col gap-3 shadow-xl min-h-[260px] lg:min-h-[300px]">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
                <History className="h-4 w-4 text-emerald-400 shrink-0" />
                تاریخچه ثبت شده
              </div>
              <span className="text-[10px] font-mono text-zinc-500">{history.length} آیتم</span>
            </div>

            <div className="flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden space-y-2 max-h-[300px] lg:max-h-[380px] select-none">
              {history.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-zinc-600 py-12">
                  هنوز رکوردی ثبت نشده است
                </div>
              ) : (
                history.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border border-zinc-800/70 bg-zinc-950/40 px-2.5 sm:px-3 py-2 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex px-1.5 sm:px-2 py-0.5 items-center justify-center rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono font-bold text-[11px] sm:text-xs">
                        {item.label}
                      </span>
                      <span className="text-zinc-400 font-mono text-[10px] sm:text-[11px]">
                        {Math.round(item.confidence * 100)}%
                      </span>
                      <span className="text-[9px] sm:text-[10px] text-zinc-500 font-mono">
                        ({item.mode})
                      </span>
                    </div>
                    <span className="text-zinc-500 font-mono text-[10px]">{item.time}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
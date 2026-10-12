"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { authApi } from "@/lib/api";
import {
  Lock,
  Mail,
  User,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
} from "lucide-react";

function AuthFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isVerifiedFromRedirect = searchParams.get("verified") === "true";

  const { login } = useAuth();
  const [tab, setTab] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(
    isVerifiedFromRedirect
      ? "ایمیل شما با موفقیت تأیید شد. اکنون وارد شوید."
      : null
  );

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const clearMessages = () => {
    setError(null);
    setSuccessMsg(null);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);

    try {
      await authApi.register({
        username: username.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      router.push(`/verify?email=${encodeURIComponent(email.trim().toLowerCase())}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);

    try {
      const targetIdentifier = username || email;
      const res = await authApi.login({
        username_or_email: targetIdentifier.trim(),
        password,
      });
      await login(res.access_token);
    } catch (err: any) {
      if (err.message.includes("تأیید")) {
        const targetEmail = email || (username.includes("@") ? username : "");
        if (targetEmail) {
          router.push(`/verify?email=${encodeURIComponent(targetEmail.trim().toLowerCase())}`);
          return;
        }
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Alert ها */}
      {error && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="leading-relaxed">{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="leading-relaxed">{successMsg}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-950 p-1 border border-zinc-800/80 mb-5">
        <button
          type="button"
          onClick={() => {
            clearMessages();
            setTab("login");
          }}
          className={`inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
            tab === "login"
              ? "bg-zinc-800 text-zinc-100 shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          ورود
        </button>
        <button
          type="button"
          onClick={() => {
            clearMessages();
            setTab("register");
          }}
          className={`inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
            tab === "register"
              ? "bg-zinc-800 text-zinc-100 shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          ثبت‌نام
        </button>
      </div>

      {/* Login Form */}
      {tab === "login" && (
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-300">
              نام کاربری یا ایمیل
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="username یا user@mail.com"
                className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
              />
              <User className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-300">
              رمز عبور
            </label>
            <div className="relative">
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
              />
              <Lock className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-emerald-600 text-white shadow hover:bg-emerald-500 h-9 px-4 py-2 w-full gap-2 mt-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "ورود به حساب"}
          </button>
        </form>
      )}

      {/* Register Form */}
      {tab === "register" && (
        <form onSubmit={handleRegister} className="space-y-3.5">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-300">
              نام کاربری
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="مثال: parsa"
                className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
              />
              <User className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-300">
              آدرس ایمیل
            </label>
            <div className="relative">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@mail.com"
                className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
              />
              <Mail className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-300">
              رمز عبور
            </label>
            <div className="relative">
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="حداقل ۶ کاراکتر"
                className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
              />
              <Lock className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-emerald-600 text-white shadow hover:bg-emerald-500 h-9 px-4 py-2 w-full gap-2 mt-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "ادامه و دریافت کد تأیید"}
          </button>
        </form>
      )}
    </>
  );
}

export default function AuthPage() {
  return (
    <div
      dir="rtl"
      className="min-h-screen w-full flex items-center justify-center p-4 bg-zinc-950 text-zinc-50 relative selection:bg-emerald-500/20 selection:text-emerald-400 font-sans"
    >
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#27272a15_1px,transparent_1px),linear-gradient(to_bottom,#27272a15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col space-y-1.5 text-center mb-6">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 mb-2">
            <Sparkles className="h-5 w-5" />
          </div>
          <h3 className="font-semibold tracking-tight text-xl text-zinc-100">
            سیستم ترجمه زبان اشاره
          </h3>
          <p className="text-xs text-zinc-400">
            ورود یا عضویت در سامانه هوشمند
          </p>
        </div>

        <Suspense
          fallback={
            <div className="flex h-44 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
            </div>
          }
        >
          <AuthFormContent />
        </Suspense>
      </div>
    </div>
  );
}

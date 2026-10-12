"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext"; // اضافه شد
import { authApi } from "@/lib/api";
import {
  KeyRound,
  Mail,
  Loader2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";

function VerifyForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth(); // متد ست کردن توکن در کوکی و استیت

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const emailParam = searchParams.get("email");
    if (emailParam) {
      setEmail(emailParam);
    }
  }, [searchParams]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await authApi.verify({
        email: email.trim().toLowerCase(),
        code: code.trim(),
      });

      if (res?.access_token) {
        
        await login(res.access_token);
      } else {
        router.push("/auth?verified=true");
      }
    } catch (err: any) {
      setError(err.message || "خطایی در تأیید کد رخ داد");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleVerify} className="space-y-4">
      {error && (
        <div className="flex items-start gap-2.5 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="leading-relaxed">{error}</span>
        </div>
      )}

      {/* ایمیل مقصد */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-zinc-300">
          ایمیل مقصد
        </label>
        <div className="relative">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="example@mail.com"
            className="flex h-9 w-full rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9 font-mono"
          />
          <Mail className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
        </div>
      </div>

      {/* کد ۶ رقمی */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-zinc-300">
          کد ۶ رقمی
        </label>
        <div className="relative">
          <input
            type="text"
            required
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.trim())}
            placeholder="••••••"
            autoFocus
            className="flex h-10 w-full text-center tracking-[0.5em] font-mono text-sm font-semibold rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-1 text-zinc-100 shadow-sm placeholder:tracking-normal placeholder:text-zinc-600 focus-visible:outline-none focus-visible:border-emerald-500 focus-visible:ring-1 focus-visible:ring-emerald-500 pl-9"
          />
          <KeyRound className="absolute left-3 top-3 h-4 w-4 text-zinc-500" />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || code.length !== 6 || !email}
        className="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-emerald-600 text-white shadow hover:bg-emerald-500 h-9 px-4 py-2 w-full gap-2 mt-2 disabled:opacity-50"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "تأیید و ورود مستقیم"}
      </button>

      <button
        type="button"
        onClick={() => router.push("/auth")}
        className="w-full text-center text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex items-center justify-center gap-1.5 pt-1"
      >
        <ArrowRight className="h-3.5 w-3.5" />
        بازگشت به صفحه ورود
      </button>
    </form>
  );
}

export default function VerifyPage() {
  return (
    <div
      dir="rtl"
      className="min-h-screen w-full flex items-center justify-center p-4 bg-zinc-950 text-zinc-50 relative selection:bg-emerald-500/20 selection:text-emerald-400 font-sans"
    >
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#27272a15_1px,transparent_1px),linear-gradient(to_bottom,#27272a15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="relative w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col space-y-1.5 text-center mb-6">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 mb-2">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h3 className="font-semibold tracking-tight text-xl text-zinc-100">
            تأیید حساب کاربری
          </h3>
          <p className="text-xs text-zinc-400">
            کد ۶ رقمی ارسال‌شده به ایمیلتان را وارد کنید
          </p>
        </div>

        <Suspense
          fallback={
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
            </div>
          }
        >
          <VerifyForm />
        </Suspense>
      </div>
    </div>
  );
}

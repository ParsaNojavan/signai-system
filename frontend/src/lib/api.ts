import Cookies from "js-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const TOKEN_KEY = "sign_auth_token";

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = Cookies.get(TOKEN_KEY);

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "خطایی در برقراری ارتباط با سرور رخ داد.");
  }

  return data;
}

// اینترفیس‌های هماهنگ با Pydantic بک‌اند شما
export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

export interface VerifyPayload {
  email: string;
  code: string;
}

export interface LoginPayload {
  username_or_email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string | number;
  username: string;
  email: string;
  role?: string;
  is_active: boolean;
  is_verified: boolean;
}

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiFetch<{ message: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  verify: (payload: VerifyPayload) =>
    apiFetch<{ message: string }>("/auth/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: LoginPayload) =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  me: () => apiFetch<UserResponse>("/auth/me"),
};

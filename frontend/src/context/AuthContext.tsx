"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import Cookies from "js-cookie";
import { useRouter } from "next/navigation";
import { TOKEN_KEY, authApi, UserResponse } from "@/lib/api";

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const fetchCurrentUser = async () => {
    try {
      const userData = await authApi.me();
      setUser(userData);
    } catch {
      Cookies.remove(TOKEN_KEY);
      setToken(null);
      setUser(null);
    }
  };

  useEffect(() => {
    const savedToken = Cookies.get(TOKEN_KEY);
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (newToken: string) => {
    Cookies.set(TOKEN_KEY, newToken, {
      expires: 7,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });
    setToken(newToken);
    await fetchCurrentUser();
    router.push("/dashboard");
  };

  const logout = () => {
    Cookies.remove(TOKEN_KEY);
    setToken(null);
    setUser(null);
    router.push("/auth");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        refreshUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth باید درون AuthProvider صدا زده شود");
  }
  return context;
};

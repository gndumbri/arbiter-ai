"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";

interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Mock check auth status
    const stored = localStorage.getItem("arbiter_user");
    if (stored) {
      setUser(JSON.parse(stored));
    }
    setIsLoading(false);
  }, []);

  const login = () => {
    // Mock login
    const mockUser = {
      id: "user_123",
      name: "Demo User",
      email: "demo@arbiter.ai",
      avatar: "https://github.com/shadcn.png"
    };
    localStorage.setItem("arbiter_user", JSON.stringify(mockUser));
    setUser(mockUser);
    router.push("/dashboard");
  };

  const logout = () => {
    localStorage.removeItem("arbiter_user");
    setUser(null);
    router.push("/");
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

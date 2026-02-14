"use client";

import Link from "next/link";
import { Shield } from "lucide-react";
import { UserMenu } from "@/components/auth/UserMenu";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="border-b border-zinc-800 bg-zinc-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex h-16 items-center px-4 md:px-8">
          <Link href="/dashboard" className="flex items-center space-x-2 font-bold md:mr-6 text-violet-500 hover:text-violet-400 transition-colors">
            <Shield className="h-6 w-6" />
            <span className="hidden md:inline-block">Arbiter AI</span>
          </Link>
          <nav className="flex items-center space-x-4 lg:space-x-6 mx-6">
            <Link
              href="/dashboard"
              className="text-sm font-medium transition-colors hover:text-violet-400 text-zinc-400"
            >
              Library
            </Link>
          </nav>
          <div className="ml-auto flex items-center space-x-4">
            <UserMenu />
          </div>
        </div>
      </div>
      <main className="flex-1 space-y-4 p-8 pt-6">
        {children}
      </main>
    </div>
  );
}


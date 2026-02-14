"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Bot, CheckCircle, Shield } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const { user, login } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 hidden md:flex">
            <Link href="/" className="mr-6 flex items-center space-x-2">
              <Shield className="h-6 w-6" />
              <span className="hidden font-bold sm:inline-block">Arbiter AI</span>
            </Link>
          </div>
          <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
            <nav className="flex items-center">
              {user ? (
                <Button asChild variant="ghost">
                  <Link href="/dashboard">Dashboard</Link>
                </Button>
              ) : (
                <Button variant="ghost" onClick={login}>
                  Login
                </Button>
              )}
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <section className="space-y-6 pb-8 pt-6 md:pb-12 md:pt-10 lg:py-32">
          <div className="container flex max-w-[64rem] flex-col items-center gap-4 text-center">
            <h1 className="font-heading text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tighter">
              The AI Referee for Your Board Games
            </h1>
            <p className="max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
              Upload your rulebook. Resolve disputes instantly. Arbiter AI validates queries against game rules with precision and citations.
            </p>
            <div className="space-x-4">
              {user ? (
                <Button asChild size="lg">
                  <Link href="/dashboard">Go to Dashboard <ArrowRight className="ml-2 h-4 w-4" /></Link>
                </Button>
              ) : (
                <Button onClick={login} size="lg">
                  Try Demo Session
                </Button>
              )}
            </div>
          </div>
        </section>
        <section
          id="features"
          className="container space-y-6 bg-slate-50 py-8 dark:bg-transparent md:py-12 lg:py-24"
        >
          <div className="mx-auto flex max-w-[58rem] flex-col items-center space-y-4 text-center">
            <h2 className="font-heading text-3xl leading-[1.1] sm:text-3xl md:text-6xl font-bold">
              Features
            </h2>
            <p className="max-w-[85%] leading-normal text-muted-foreground sm:text-lg sm:leading-7">
              Built with advanced RAG technology to understand complex rule interactions.
            </p>
          </div>
          <div className="mx-auto grid justify-center gap-4 sm:grid-cols-2 md:max-w-[64rem] md:grid-cols-3">
            <div className="relative overflow-hidden rounded-lg border bg-background p-2">
              <div className="flex h-[180px] flex-col justify-between rounded-md p-6">
                <BookOpen className="h-12 w-12" />
                <div className="space-y-2">
                  <h3 className="font-bold">Rule Ingestion</h3>
                  <p className="text-sm text-muted-foreground">
                    Upload PDFs and get instant semantic indexing.
                  </p>
                </div>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-lg border bg-background p-2">
              <div className="flex h-[180px] flex-col justify-between rounded-md p-6">
                <Bot className="h-12 w-12" />
                <div className="space-y-2">
                  <h3 className="font-bold">AI Judge</h3>
                  <p className="text-sm text-muted-foreground">
                    Ask complex questions and get verdicts with citations.
                  </p>
                </div>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-lg border bg-background p-2">
              <div className="flex h-[180px] flex-col justify-between rounded-md p-6">
                <CheckCircle className="h-12 w-12" />
                <div className="space-y-2">
                  <h3 className="font-bold">Conflict Resolution</h3>
                  <p className="text-sm text-muted-foreground">
                    Handles errata and expansion conflicts automatically.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="py-6 md:px-8 md:py-0">
        <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            Built by Arbiter AI Team.
          </p>
        </div>
      </footer>
    </div>
  );
}

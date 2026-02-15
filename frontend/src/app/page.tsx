"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Bot, CheckCircle, Shield } from "lucide-react";
import { useSession, signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const { data: session } = useSession();
  const user = session?.user;

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-16 max-w-6xl items-center px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center space-x-2">
            <Shield className="h-6 w-6 text-primary" />
            <span className="font-bold text-lg">Arbiter AI</span>
          </Link>
          <div className="ml-auto flex items-center space-x-2">
            {user ? (
              <Button asChild variant="ghost">
                <Link href="/dashboard">Dashboard</Link>
              </Button>
            ) : (
              <Button variant="ghost" onClick={() => signIn()}>
                Login
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden py-20 sm:py-28 lg:py-36">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/15 rounded-full blur-[120px] -z-10" />

          <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 px-4 text-center sm:px-6 lg:px-8">
            <div className="rounded-full bg-muted px-4 py-1.5 text-sm font-medium text-muted-foreground border border-primary/20">
              Arbiter AI v1.0 Now Live
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-br from-foreground to-muted-foreground">
              The AI Referee{" "}
              <br className="hidden sm:inline" />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">
                For Your Tabletop.
              </span>
            </h1>
            <p className="max-w-2xl leading-relaxed text-muted-foreground text-base sm:text-lg md:text-xl">
              Stop arguing about line-of-sight and obscure errata. Upload your
              rulebooks and let our Agentic AI resolve disputes instantly with
              citations.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
              {user ? (
                <Button asChild size="lg" className="rounded-full shadow-lg shadow-primary/20">
                  <Link href="/dashboard">
                    Resume Campaign <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              ) : (
                <Button
                  onClick={() => signIn()}
                  size="lg"
                  className="rounded-full px-8 text-lg shadow-lg shadow-primary/20 hover:scale-105 transition-transform"
                >
                  Roll for Initiative
                </Button>
              )}
              <Button asChild variant="outline" size="lg" className="rounded-full">
                <Link href="#features">Learn More</Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="border-t border-border/40 py-16 sm:py-20 lg:py-28">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center space-y-4 text-center mb-12">
              <h2 className="font-heading text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight">
                Features
              </h2>
              <p className="max-w-2xl text-muted-foreground sm:text-lg leading-relaxed">
                Built with advanced RAG technology to understand complex rule interactions.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="group relative overflow-hidden rounded-xl border border-border/50 bg-card p-6 transition-colors hover:border-primary/40 hover:bg-card/80">
                <div className="flex flex-col gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <BookOpen className="h-6 w-6 text-primary" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-bold text-lg">Rule Ingestion</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Upload your rulebooks as PDFs and get instant semantic indexing for lightning-fast lookups.
                    </p>
                  </div>
                </div>
              </div>

              <div className="group relative overflow-hidden rounded-xl border border-border/50 bg-card p-6 transition-colors hover:border-primary/40 hover:bg-card/80">
                <div className="flex flex-col gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-secondary/10">
                    <Bot className="h-6 w-6 text-secondary" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-bold text-lg">AI Game Master</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Ask complex rules questions and get authoritative verdicts with page-level citations.
                    </p>
                  </div>
                </div>
              </div>

              <div className="group relative overflow-hidden rounded-xl border border-border/50 bg-card p-6 transition-colors hover:border-primary/40 hover:bg-card/80">
                <div className="flex flex-col gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-500/10">
                    <CheckCircle className="h-6 w-6 text-green-500" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-bold text-lg">Conflict Resolution</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Handles errata and expansion conflicts automatically. No more table-flip arguments.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/40 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} Arbiter AI. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

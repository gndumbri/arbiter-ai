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
                <Button variant="ghost" onClick={() => signIn()}>
                  Login
                </Button>
              )}
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <section className="space-y-6 pb-8 pt-6 md:pb-12 md:pt-10 lg:py-32 relative overflow-hidden">
           {/* Background Gradient Blob */}
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/20 rounded-full blur-3xl -z-10 animate-pulse" />

          <div className="container flex max-w-[64rem] flex-col items-center gap-4 text-center">
            <div className="rounded-2xl bg-muted px-4 py-1.5 text-sm font-medium text-muted-foreground mb-4 border border-primary/20">
              Arbiter AI v1.0 Now Live
            </div>
            <h1 className="font-heading text-4xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-br from-foreground to-muted-foreground">
              The AI Referee <br className="hidden sm:inline" />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">
                For Your Tabletop.
              </span>
            </h1>
            <p className="max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8 mt-4">
              Stop arguing about line-of-sight and obscure errata. Upload your rulebooks and let our Agentic AI resolve disputes instantly with citations.
            </p>
            <div className="space-x-4 mt-8">
              {user ? (
                <Button asChild size="lg" className="rounded-full shadow-lg shadow-primary/20">
                  <Link href="/dashboard">Resume Campaign <ArrowRight className="ml-2 h-4 w-4" /></Link>
                </Button>
              ) : (
                <Button onClick={() => signIn()} size="lg" className="rounded-full px-8 text-lg shadow-lg shadow-primary/20 hover:scale-105 transition-transform">
                  Roll for Initiative
                </Button>
              )}
              <Button asChild variant="outline" size="lg" className="rounded-full">
                <Link href="#features">Learn More</Link>
              </Button>
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
                <BookOpen className="h-12 w-12 text-violet-500" />
                <div className="space-y-2">
                  <h3 className="font-bold">Rule Ingestion (Library)</h3>
                  <p className="text-sm text-muted-foreground">
                    Upload your tomes (PDFs) and get instant semantic indexing.
                  </p>
                </div>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-lg border bg-background p-2">
              <div className="flex h-[180px] flex-col justify-between rounded-md p-6">
                <Bot className="h-12 w-12 text-indigo-500" />
                <div className="space-y-2">
                  <h3 className="font-bold">AI Game Master</h3>
                  <p className="text-sm text-muted-foreground">
                    Ask complex rules questions and get verdicts with citations.
                  </p>
                </div>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-lg border bg-background p-2">
              <div className="flex h-[180px] flex-col justify-between rounded-md p-6">
                <CheckCircle className="h-12 w-12 text-green-500" />
                <div className="space-y-2">
                  <h3 className="font-bold">Conflict Resolution</h3>
                  <p className="text-sm text-muted-foreground">
                    Handles errata and expansion conflicts. No more table flip arguments.
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

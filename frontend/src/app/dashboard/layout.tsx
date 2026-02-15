"use client";

import Link from "next/link";
import { Shield, Settings } from "lucide-react";
import { UserMenu } from "@/components/auth/UserMenu";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const navItems = [
    { href: "/dashboard", label: "Shelf" },
    { href: "/dashboard/catalog", label: "Armory" },
    { href: "/dashboard/rulings", label: "Scrolls" },
    { href: "/dashboard/parties", label: "Guild" },
    { href: "/dashboard/agents", label: "Ask" },
    { href: "/dashboard/settings", label: "Settings" },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="border-b border-border/40 bg-background/95 backdrop-blur-sm sticky top-0 z-50">
        <div className="mx-auto flex h-14 max-w-6xl items-center px-4 sm:px-6 lg:px-8">
          <Link
            href="/dashboard"
            className="flex items-center space-x-2 font-bold text-primary hover:text-primary/80 transition-colors shrink-0"
          >
            <Shield className="h-5 w-5" />
            <span className="hidden sm:inline-block">Arbiter AI</span>
          </Link>
          <nav className="flex items-center space-x-1 ml-4 sm:ml-6 overflow-x-auto scrollbar-hide">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "px-2 sm:px-3 py-1.5 text-sm font-medium rounded-md transition-colors whitespace-nowrap shrink-0",
                  pathname === item.href
                    ? "text-foreground bg-muted"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center space-x-4">
            <UserMenu />
          </div>
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>
    </div>
  );
}

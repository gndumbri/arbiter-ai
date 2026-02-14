/**
 * AdminPage.tsx — Admin Portal with system stats, user/publisher/tier management.
 *
 * Fetches data from GET /api/v1/admin/* endpoints (admin-only).
 * Displays stats cards in Overview tab, and management tables in
 * Users, Publishers, and Tiers tabs.
 *
 * Used by: /dashboard/admin route
 */
"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Users, ScrollText, Gamepad2, Building2, BarChart3, Shield } from "lucide-react";
import { motion } from "framer-motion";

interface AdminStats {
  total_users: number;
  total_sessions: number;
  total_queries: number;
  total_rulesets: number;
  total_publishers: number;
}

interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string | null;
}

interface AdminPublisher {
  id: string;
  name: string;
  slug: string;
  contact_email: string;
  verified: boolean;
  created_at: string | null;
}

interface AdminTier {
  id: string;
  name: string;
  daily_query_limit: number;
}

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [publishers, setPublishers] = useState<AdminPublisher[]>([]);
  const [tiers, setTiers] = useState<AdminTier[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "publishers" | "tiers">("overview");

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const headers = {
    "Content-Type": "application/json",
    Authorization: "Bearer dev-token",
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (activeTab === "users") fetchUsers();
    if (activeTab === "publishers") fetchPublishers();
    if (activeTab === "tiers") fetchTiers();
  }, [activeTab]);

  async function fetchStats() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/stats`, { headers });
      if (res.ok) setStats(await res.json());
    } catch {}
  }
  async function fetchUsers() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/users`, { headers });
      if (res.ok) setUsers(await res.json());
    } catch {}
  }
  async function fetchPublishers() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/publishers`, { headers });
      if (res.ok) setPublishers(await res.json());
    } catch {}
  }
  async function fetchTiers() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/tiers`, { headers });
      if (res.ok) setTiers(await res.json());
    } catch {}
  }

  const statCards = stats
    ? [
        { label: "Users", value: stats.total_users, icon: Users, color: "text-violet-400" },
        { label: "Sessions", value: stats.total_sessions, icon: Gamepad2, color: "text-cyan-400" },
        { label: "Queries", value: stats.total_queries, icon: ScrollText, color: "text-emerald-400" },
        { label: "Rulesets", value: stats.total_rulesets, icon: BarChart3, color: "text-amber-400" },
        { label: "Publishers", value: stats.total_publishers, icon: Building2, color: "text-rose-400" },
      ]
    : [];

  const tabs = [
    { id: "overview" as const, label: "Overview" },
    { id: "users" as const, label: "Users" },
    { id: "publishers" as const, label: "Publishers" },
    { id: "tiers" as const, label: "Tiers" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-violet-400" />
            Admin Portal
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            System overview, user management, and configuration.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-muted/30 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"
        >
          {statCards.map((s, i) => (
            <Card key={s.label} className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">{s.label}</p>
                    <p className="text-2xl font-bold mt-1">{s.value}</p>
                  </div>
                  <s.icon className={`h-8 w-8 ${s.color} opacity-60`} />
                </div>
              </CardContent>
            </Card>
          ))}
        </motion.div>
      )}

      {/* Users Tab */}
      {activeTab === "users" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
              <CardTitle>Users</CardTitle>
              <CardDescription>Manage user roles and permissions.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {users.length === 0 && (
                  <p className="text-muted-foreground text-sm">No users found.</p>
                )}
                {users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                    <div>
                      <p className="font-medium text-sm">{u.name || u.email}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                    <Badge variant={u.role === "ADMIN" ? "default" : "secondary"} className="text-xs">
                      {u.role}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Publishers Tab */}
      {activeTab === "publishers" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
              <CardTitle>Publishers</CardTitle>
              <CardDescription>Manage registered publishers and API keys.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {publishers.length === 0 && (
                  <p className="text-muted-foreground text-sm">No publishers registered.</p>
                )}
                {publishers.map((p) => (
                  <div key={p.id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                    <div>
                      <p className="font-medium text-sm">{p.name}</p>
                      <p className="text-xs text-muted-foreground">{p.contact_email} • {p.slug}</p>
                    </div>
                    <Badge variant={p.verified ? "default" : "outline"} className="text-xs">
                      {p.verified ? "Verified" : "Unverified"}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Tiers Tab */}
      {activeTab === "tiers" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
              <CardTitle>Subscription Tiers</CardTitle>
              <CardDescription>Configure daily query limits per tier.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {tiers.length === 0 && (
                  <p className="text-muted-foreground text-sm">No tiers configured. Seed the database.</p>
                )}
                {tiers.map((t) => (
                  <div key={t.id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                    <div>
                      <p className="font-medium text-sm">{t.name}</p>
                    </div>
                    <Badge variant="outline" className="text-xs font-mono">
                      {t.daily_query_limit === -1 ? "Unlimited" : `${t.daily_query_limit}/day`}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

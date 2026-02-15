"use client";

import Link from "next/link";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Loader2, Bot, Plus, MessageSquare, Settings } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function AgentsPage() {
  const { data: agents, error, isLoading } = useSWR("agents", api.listAgents, {
    refreshInterval: 0, 
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">My NPCs</h2>
          <p className="text-muted-foreground text-sm sm:text-base">Custom AI personas trained on your rulesets.</p>
        </div>
        <Button asChild className="w-full sm:w-auto">
          <Link href="/dashboard/agents/new">
            <Plus className="mr-2 h-4 w-4" />
            Recruit NPC
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="rounded-md bg-destructive/15 p-4 text-destructive">
          Failed to load agents.
        </div>
      ) : agents?.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Bot className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">No NPCs on payroll</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Recruit one to answer rules questions your way.
          </p>
          <Button asChild>
            <Link href="/dashboard/agents/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Agent
            </Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {agents?.map((agent, index) => (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
            >
              <Card className="flex flex-col h-full hover:shadow-lg hover:border-primary/50 transition-all duration-300">
                <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="overflow-hidden text-ellipsis whitespace-nowrap text-lg font-bold w-full pr-2" title={agent.game_name}>
                    {agent.game_name}
                  </CardTitle>
                  <Bot className="h-5 w-5 text-primary" />
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="text-sm text-muted-foreground space-y-2">
                    {agent.persona && (
                      <p className="line-clamp-2 text-xs italic">
                        &quot;{agent.persona}&quot;
                      </p>
                    )}
                    <p className="text-xs">
                       Created {formatDistanceToNow(new Date(agent.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </CardContent>
                <CardFooter className="flex gap-2">
                  <Button asChild className="flex-1" variant="secondary"> 
                    <Link href={`/session/${agent.id}`}>
                      <MessageSquare className="mr-2 h-4 w-4" />
                      Consult
                    </Link>
                  </Button>
                  <EmbedButton agentId={agent.id} />
                </CardFooter>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmbedButton({ agentId }: { agentId: string }) {
  const { toast } = useToast();
  
  const handleCopy = () => {
    const code = `<iframe src="${window.location.origin}/widget/${agentId}" width="400" height="600" style="border:none; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);"></iframe>`;
    navigator.clipboard.writeText(code);
    toast({ title: "Copied!", description: "Embed code copied to clipboard." });
  };

  return (
    <Button variant="outline" size="icon" onClick={handleCopy} title="Copy Embed Code">
      <Settings className="h-4 w-4" />
    </Button>
  );
}

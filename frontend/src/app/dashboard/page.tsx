"use client";

import Link from "next/link";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Loader2, MessageSquare, FileText, CheckCircle, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RulesetUploadDialog } from "@/components/dashboard/RulesetUploadDialog";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { data: rulesets, error, isLoading } = useSWR("rulesets", api.listRulesets, {
    refreshInterval: 5000, 
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Game Library</h2>
          <p className="text-muted-foreground">Manage your rulesets and start sessions.</p>
        </div>
        <RulesetUploadDialog />
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="rounded-md bg-destructive/15 p-4 text-destructive">
          Failed to load rulesets. Is the backend running?
        </div>
      ) : rulesets?.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed text-center">
          <FileText className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">No rulesets yet</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Upload a PDF rulebook to get started.
          </p>
          <RulesetUploadDialog />
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {rulesets?.map((ruleset, index) => (
            <motion.div
              key={ruleset.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
            >
              <Card className="flex flex-col h-full hover:shadow-lg hover:border-primary/50 transition-all duration-300">
                <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="overflow-hidden text-ellipsis whitespace-nowrap text-lg font-bold w-full pr-2" title={ruleset.game_name}>
                    {ruleset.game_name}
                  </CardTitle>
                  <StatusBadge status={ruleset.status} />
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p className="truncate font-mono text-xs" title={ruleset.filename}>{ruleset.filename}</p>
                    <p className="text-xs">
                      <span className="font-semibold text-foreground">{ruleset.chunk_count}</span> Rules Indexed
                    </p>
                    <p className="text-xs">
                      {ruleset.created_at
                        ? formatDistanceToNow(new Date(ruleset.created_at), { addSuffix: true })
                        : "Recently"}
                    </p>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button asChild className="w-full relative group overflow-hidden" disabled={ruleset.status !== "INDEXED" && ruleset.status !== "COMPLETE" && ruleset.status !== "READY"}> 
                    <Link href={`/session/${ruleset.session_id}`}>
                      <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" />
                      <MessageSquare className="mr-2 h-4 w-4" />
                      Start Session
                    </Link>
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "INDEXED" || status === "COMPLETE") {
    return (
      <Badge variant="outline" className="border-green-500 text-green-500">
        <CheckCircle className="mr-1 h-3 w-3" />
        Ready
      </Badge>
    );
  }
  if (status === "FAILED") {
    return (
      <Badge variant="destructive">
        <AlertCircle className="mr-1 h-3 w-3" />
        Failed
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="animate-pulse">
      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
      {status}
    </Badge>
  );
}

"use client";

import Link from "next/link";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Loader2, MessageSquare, FileText, CheckCircle, AlertCircle } from "lucide-react";
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
          {rulesets?.map((ruleset) => (
            <Card key={ruleset.id} className="flex flex-col">
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="overflow-hidden text-ellipsis whitespace-nowrap text-lg font-semibold w-full pr-2" title={ruleset.game_name}>
                  {ruleset.game_name}
                </CardTitle>
                <StatusBadge status={ruleset.status} />
              </CardHeader>
              <CardContent className="flex-1">
                <div className="text-sm text-muted-foreground space-y-1">
                  <p className="truncate" title={ruleset.filename}>{ruleset.filename}</p>
                  <p>Chunks: {ruleset.chunk_count}</p>
                  <p>
                    Uploaded{" "}
                    {ruleset.created_at
                      ? formatDistanceToNow(new Date(ruleset.created_at), { addSuffix: true })
                      : "Recently"}
                  </p>
                </div>
              </CardContent>
              <CardFooter>
                <Button asChild className="w-full" disabled={ruleset.status !== "INDEXED" && ruleset.status !== "COMPLETE"}> 
                  {/* Status might be INDEXED or COMPLETE depending on backend - rules.py used INDEXED in Phase 2, but recent edit used PROCESSING. Logic should check. */}
                  <Link href={`/session/${ruleset.session_id}`}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    Start Session
                  </Link>
                </Button>
              </CardFooter>
            </Card>
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

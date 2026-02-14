import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, FileText, AlertTriangle, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  verdict?: any; // strict typing later
  onCitationClick?: (citation: any) => void;
}

export function MessageBubble({ role, content, verdict, onCitationClick }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={cn("flex w-full gap-3 p-4", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <Avatar className="h-8 w-8 border">
          <AvatarFallback><Bot className="h-4 w-4" /></AvatarFallback>
          <AvatarImage src="/bot-avatar.png" />
        </Avatar>
      )}

      <div className={cn(
        "flex max-w-[85%] flex-col gap-2 rounded-lg p-4",
        isUser ? "bg-primary text-primary-foreground" : "bg-muted"
      )}>
        <div className="prose prose-sm dark:prose-invert break-words">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>

        {verdict && (
          <div className="mt-4 space-y-3 border-t pt-3">
            {/* Verdict meta */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium">Confidence:</span>
              <Badge variant={verdict.confidence > 0.8 ? "default" : "secondary"} className={cn("px-1 py-0 text-[10px]", verdict.confidence > 0.8 ? "bg-green-600" : "bg-yellow-600")}>
                {Math.round(verdict.confidence * 100)}%
              </Badge>
            </div>

            {/* Citations */}
            {verdict.citations && verdict.citations.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {verdict.citations.map((citation: any, i: number) => (
                  <Button
                    key={i}
                    variant="outline"
                    size="sm"
                    className="h-6 gap-1 text-xs bg-background/50"
                    onClick={() => onCitationClick?.(citation)}
                  >
                    <FileText className="h-3 w-3" />
                    {citation.source} {citation.page ? `p.${citation.page}` : ""}
                  </Button>
                ))}
              </div>
            )}

            {/* Conflicts / Reasoning */}
            {(verdict.conflicts?.length > 0 || verdict.reasoning_chain) && (
              <Accordion type="single" collapsible className="w-full">
                {verdict.conflicts?.length > 0 && (
                  <AccordionItem value="conflicts" className="border-b-0">
                    <AccordionTrigger className="py-2 text-xs font-medium text-amber-600 dark:text-amber-400">
                      <div className="flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" />
                        Conflicts Detected ({verdict.conflicts.length})
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="text-xs">
                      <ul className="list-disc pl-4 space-y-1">
                        {verdict.conflicts.map((c: any, i: number) => (
                          <li key={i}>
                            <span className="font-semibold">Conflict:</span> {c.description}
                            <br />
                            <span className="font-semibold text-green-600">Resolution:</span> {c.resolution}
                          </li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                )}
                
                 {verdict.reasoning_chain && (
                  <AccordionItem value="reasoning" className="border-b-0">
                    <AccordionTrigger className="py-2 text-xs font-medium text-muted-foreground">
                       <div className="flex items-center gap-1">
                        <Lightbulb className="h-3 w-3" />
                        Show Reasoning
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-background/50 p-2 rounded">
                      {verdict.reasoning_chain}
                    </AccordionContent>
                  </AccordionItem>
                )}
              </Accordion>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <Avatar className="h-8 w-8">
          <AvatarFallback><User className="h-4 w-4" /></AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}

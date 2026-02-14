import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Lightbulb, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { motion } from "framer-motion";

interface MessageBubbleProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    verdict?: any;
    timestamp?: Date;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onCitationClick?: (citation: any) => void;
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const { verdict } = message;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex w-full gap-3 md:gap-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <Avatar className={cn("h-8 w-8 md:h-10 md:w-10 ring-2 ring-offset-2 ring-offset-background", isUser ? "ring-secondary" : "ring-primary")}>
        {isUser ? (
          <AvatarFallback className="bg-secondary text-secondary-foreground font-bold">ME</AvatarFallback>
        ) : (
          <AvatarFallback className="bg-primary text-primary-foreground font-bold">AI</AvatarFallback>
        )}
      </Avatar>

      <div className={cn("flex flex-col gap-2 max-w-[85%] md:max-w-[75%]", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-5 py-4 text-sm md:text-base shadow-lg relative overflow-hidden",
            isUser
              ? "bg-secondary text-secondary-foreground rounded-tr-sm"
              : "bg-card text-card-foreground border border-border/50 rounded-tl-sm"
          )}
        >
          {/* Subtle gradient overlay for AI bubbles */}
          {!isUser && (
             <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />
          )}

          {/* Verdict Badge */}
          {verdict && !isUser && (
            <div className="relative mb-3 flex flex-wrap items-center gap-2 border-b border-border/10 pb-2">
               <Badge 
                  variant={verdict.verdict.includes("ALLOW") ? "outline" : "destructive"}
                  className={cn(
                    "text-xs uppercase tracking-wider font-bold shadow-sm",
                     verdict.verdict.includes("ALLOW") ? "border-green-500/50 text-green-500" : "border-red-500/50"
                  )}
                >
                 {verdict.verdict}
               </Badge>
               {verdict.confidence && (
                 <span className="text-xs text-muted-foreground font-mono">
                   {Math.round(verdict.confidence * 100)}% CONFIDENCE
                 </span>
               )}
            </div>
          )}

          {/* Reasoning Chain Collapsible */}
           {verdict && verdict.reasoning_chain && (
             <Accordion type="single" collapsible className="relative mb-3 w-full border-b border-border/10">
               <AccordionItem value="reasoning" className="border-none">
                 <AccordionTrigger className="py-1 text-xs text-muted-foreground hover:text-primary hover:no-underline font-mono uppercase tracking-wider flex items-center gap-2">
                   <Lightbulb className="h-3 w-3" /> Analysis Chain
                 </AccordionTrigger>
                 <AccordionContent className="text-xs text-muted-foreground italic pl-3 border-l-2 border-primary/20 my-2">
                   <ReactMarkdown remarkPlugins={[remarkGfm]}>
                     {verdict.reasoning_chain}
                   </ReactMarkdown>
                 </AccordionContent>
               </AccordionItem>
             </Accordion>
           )}

          {/* Main Content */}
          <div className="relative prose prose-sm dark:prose-invert break-words leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        {/* Citations Grid */}
        {verdict && verdict.citations && verdict.citations.length > 0 && (
           <motion.div 
             initial={{ opacity: 0 }}
             animate={{ opacity: 1 }}
             transition={{ delay: 0.2 }}
             className="grid grid-cols-1 gap-2 sm:grid-cols-2 w-full mt-1"
           >
             {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
             {verdict.citations.map((citation: any, idx: number) => (
               <Card 
                 key={idx} 
                 className="cursor-pointer bg-card/50 hover:bg-card transition-all border-primary/20 hover:border-primary/60 group overflow-hidden"
                 onClick={() => onCitationClick?.(citation)}
               >
                 <CardContent className="p-3 flex items-start gap-3 relative">
                   <div className="absolute inset-y-0 left-0 w-1 bg-primary/20 group-hover:bg-primary transition-colors" />
                   <FileText className="h-4 w-4 text-primary mt-1 shrink-0 group-hover:scale-110 transition-transform" />
                   <div className="flex flex-col gap-1 overflow-hidden">
                     <p className="text-xs font-bold truncate text-foreground group-hover:text-primary transition-colors">
                       {citation.source_file || "Unknown Source"}
                     </p>
                     <p className="text-[10px] text-muted-foreground line-clamp-2 leading-snug">
                       &quot;{citation.text}&quot;
                     </p>
                   </div>
                 </CardContent>
               </Card>
             ))}
           </motion.div>
        )}
        
        {/* Timestamp */}
        {message.timestamp && (
            <span className="text-[10px] text-muted-foreground opacity-50 px-1 select-none">
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
        )}
      </div>
    </motion.div>
  );
}

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Lightbulb, FileText, Bookmark, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { motion } from "framer-motion";
import useSWR from "swr";
import { api } from "@/lib/api";

interface MessageBubbleProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    verdict?: any;
    timestamp?: Date;
  };
  gameName?: string;
  sessionId?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onCitationClick?: (citation: any) => void;
  onFollowUp?: (question: string) => void;
}

function ConfidencePill({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color =
    confidence >= 0.8
      ? "bg-green-500/15 text-green-400 border-green-500/30"
      : confidence >= 0.5
      ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30"
      : "bg-red-500/15 text-red-400 border-red-500/30";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-mono font-medium ${color}`}>
      {pct}%
    </span>
  );
}

export function MessageBubble({ message, gameName, sessionId, onCitationClick, onFollowUp }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const { verdict } = message;
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const privacyRef = useRef<HTMLDivElement>(null);

  // Close privacy dropdown when clicking outside
  useEffect(() => {
    if (!privacyOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (privacyRef.current && !privacyRef.current.contains(e.target as Node)) {
        setPrivacyOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [privacyOpen]);

  // Fetch profile for default ruling privacy — SWR caches across all bubbles
  const { data: profile } = useSWR("profile", api.getProfile, { onError: () => {} });
  const userDefault = (profile?.default_ruling_privacy || "PRIVATE") as "PRIVATE" | "PARTY" | "PUBLIC";

  const handleSaveRuling = async (privacy: "PRIVATE" | "PARTY" | "PUBLIC") => {
    if (!verdict || saved || saving) return;
    setSaving(true);
    setPrivacyOpen(false);
    try {
      await api.saveRuling({
        query: message.content,
        verdict_json: verdict,
        game_name: gameName,
        session_id: sessionId,
        privacy_level: privacy,
      });
      setSaved(true);
    } catch {
      // silent fail
    } finally {
      setSaving(false);
    }
  };

  const privacyOptions = [
    { value: "PRIVATE" as const, icon: "🔒", label: "Private" },
    { value: "PARTY" as const, icon: "👥", label: "Party" },
    { value: "PUBLIC" as const, icon: "🌐", label: "Public" },
  ];

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

          {/* Verdict Header */}
          {verdict && !isUser && (
            <div className="relative mb-3 flex flex-wrap items-center gap-2 border-b border-border/10 pb-2">
               {verdict.confidence !== undefined && (
                 <ConfidencePill confidence={verdict.confidence} />
               )}
               {verdict.model && (
                 <Badge variant="secondary" className="text-[10px] font-mono tracking-tighter opacity-70">
                   {verdict.model}
                 </Badge>
               )}
               {/* Save Ruling Button with Privacy Dropdown */}
               <div className="relative ml-auto" ref={privacyRef}>
                 {saved ? (
                   <Button
                     variant="ghost"
                     size="sm"
                     className="h-6 px-2 text-xs gap-1 text-green-400"
                     disabled
                   >
                     <Check className="h-3 w-3" /> Saved
                   </Button>
                 ) : (
                   <>
                     <Button
                       variant="ghost"
                       size="sm"
                       className="h-6 px-2 text-xs gap-1 text-muted-foreground hover:text-primary"
                       onClick={() => setPrivacyOpen(!privacyOpen)}
                       disabled={saving}
                     >
                       <Bookmark className="h-3 w-3" /> Save
                     </Button>
                     {privacyOpen && (
                       <div className="absolute right-0 top-full mt-1 z-50 bg-popover border border-border rounded-lg shadow-xl p-1 min-w-[140px]">
                         {privacyOptions.map((opt) => (
                           <button
                             key={opt.value}
                             className={cn(
                               "w-full flex items-center gap-2 px-3 py-1.5 text-xs rounded-md hover:bg-muted transition-colors text-left",
                               opt.value === userDefault && "bg-muted/50 font-medium"
                             )}
                             onClick={() => handleSaveRuling(opt.value)}
                           >
                             <span>{opt.icon}</span>
                             <span>{opt.label}{opt.value === userDefault ? " ★" : ""}</span>
                           </button>
                         ))}
                       </div>
                     )}
                   </>
                 )}
               </div>
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

        {/* Follow-Up Hint Chips */}
        {verdict && verdict.follow_up_hint && !isUser && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex flex-wrap gap-2 mt-1"
          >
            {verdict.follow_up_hint.split(/[?.]/).filter((h: string) => h.trim().length > 5).slice(0, 3).map((hint: string, i: number) => (
              <button
                key={i}
                className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs text-primary hover:bg-primary/10 hover:border-primary/50 transition-colors"
                onClick={() => onFollowUp?.(hint.trim() + "?")}
              >
                {hint.trim()}?
              </button>
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

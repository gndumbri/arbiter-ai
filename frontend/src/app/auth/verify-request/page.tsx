
"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MailCheck } from "lucide-react";
import { motion } from "framer-motion";

export default function VerifyRequestPage() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-background p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-violet-500/10 ring-1 ring-violet-500/50">
              <MailCheck className="h-8 w-8 text-violet-500" />
            </div>
            <CardTitle className="text-2xl font-bold">Check Your Inbox ✨</CardTitle>
            <CardDescription className="text-base text-zinc-400">
              A magic link has been sent to your email. Click it to enter the arena.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center text-sm text-zinc-500">
             If it doesn&apos;t appear, check your spam folder. You can close this tab.
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

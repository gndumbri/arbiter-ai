"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSmartBack } from "@/hooks/use-smart-back";
import { ArrowLeft, Bot, FileText, CheckCircle, Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function NewAgentPage() {
  const router = useRouter();
  const goBack = useSmartBack("/dashboard/agents");
  const { toast } = useToast();
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [agentId, setAgentId] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    gameName: "",
    npcName: "",
    persona: "Helpful Guide",
    systemPrompt: "",
  });

  // Upload State
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleCreateAgent = async () => {
    const trimmedGameName = formData.gameName.trim();
    const trimmedNpcName = formData.npcName.trim();
    if (!trimmedGameName) {
      toast({ title: "Error", description: "Game name is required", variant: "destructive" });
      return;
    }
    if (!trimmedNpcName) {
      toast({ title: "Error", description: "NPC name is required", variant: "destructive" });
      return;
    }

    const personaLabel = `${trimmedNpcName} - ${formData.persona}`;
    const customPrompt = formData.systemPrompt.trim();
    const systemPromptOverride = customPrompt || undefined;

    setIsLoading(true);
    try {
      const session = await api.createSession({
        game_name: trimmedGameName,
        persona: personaLabel,
        system_prompt_override: systemPromptOverride,
      });
      setAgentId(session.id);
      setStep(2);
      toast({ title: "Success", description: "Session created! Now add game rules." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create agent";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadRuleset = async () => {
    if (!uploadFile || !agentId) return;

    setIsUploading(true);
    try {
      const data = new FormData();
      data.append("file", uploadFile);
      data.append("game_name", formData.gameName.trim());
      data.append("source_type", "BASE");

      await api.uploadRuleset(agentId, data);
      toast({ title: "Success", description: "Ruleset uploaded and processing started." });
      setStep(3);
    } catch {
      toast({ title: "Error", description: "Upload failed", variant: "destructive" });
    } finally {
      setIsUploading(false);
    }
  };

  const handleFinish = () => {
    router.push("/dashboard/agents");
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8 py-8">
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="icon" onClick={goBack}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Start a Game Session</h2>
          <p className="text-muted-foreground">Pick a game, define your NPC arbiter style, then upload rules if needed.</p>
        </div>
      </div>

      <div className="flex items-center justify-center space-x-4">
        <StepIndicator number={1} title="Game + NPC" current={step === 1} completed={step > 1} />
        <div className="w-16 h-px bg-border" />
        <StepIndicator number={2} title="What They Know" current={step === 2} completed={step > 2} />
        <div className="w-16 h-px bg-border" />
        <StepIndicator number={3} title="Ready Check" current={step === 3} completed={step > 3} />
      </div>

      <Card>
        {step === 1 && (
          <>
            <CardHeader>
              <CardTitle>Session Setup</CardTitle>
              <CardDescription>Associate this session to a game and configure your NPC judge behavior.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="gameName">Game Name</Label>
                <Input
                  id="gameName"
                  placeholder="e.g. Catan (6th Ed), D&D 5e, Root"
                  value={formData.gameName}
                  onChange={(e) => setFormData({ ...formData, gameName: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="npcName">NPC Name</Label>
                <Input
                  id="npcName"
                  placeholder="e.g. Gandalf the Rules Nerd"
                  value={formData.npcName}
                  onChange={(e) => setFormData({ ...formData, npcName: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="persona">Persona Template</Label>
                <div className="relative">
                  <select
                    id="persona"
                    className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                    value={formData.persona}
                    onChange={(e) => setFormData({ ...formData, persona: e.target.value })}
                  >
                    <option value="Helpful Guide">Helpful Guide (Friendly, patient)</option>
                    <option value="Rule Lawyer">Rule Lawyer (Strict, technical)</option>
                    <option value="Dungeon Master">Dungeon Master (Creative, narrative)</option>
                    <option value="Custom">Custom</option>
                  </select>
                  {/* Chevron down icon for custom select styling could go here, but native is fine for now */}
                </div>
              </div>

              {formData.persona === "Custom" && (
                <div className="space-y-2">
                  <Label htmlFor="systemPrompt">Custom System Prompt</Label>
                  <Textarea
                    id="systemPrompt"
                    placeholder="You are a..."
                    value={formData.systemPrompt}
                    onChange={(e) => setFormData({ ...formData, systemPrompt: e.target.value })}
                    className="h-32"
                  />
                </div>
              )}
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleCreateAgent} disabled={isLoading || !formData.gameName || !formData.npcName}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Next: Add Knowledge
              </Button>
            </CardFooter>
          </>
        )}

        {step === 2 && agentId && (
          <>
            <CardHeader>
              <CardTitle>Add Knowledge</CardTitle>
              <CardDescription>Upload rulebooks or documents for your agent to reference.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="text-center space-y-2">
                 <Bot className="h-12 w-12 mx-auto text-primary/20" />
                 <p className="text-sm text-muted-foreground">
                   Your NPC <strong>{formData.npcName}</strong> is assigned to{" "}
                   <strong>{formData.gameName}</strong>. Upload the rules so answers stay grounded.
                 </p>
              </div>
              
              <div className="grid gap-4 border-2 border-dashed rounded-lg p-6 hover:bg-muted/50 transition-colors">
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <Label htmlFor="file" className="cursor-pointer">
                      <span className="text-primary font-semibold">Click to upload PDF</span> or drag and drop
                    </Label>
                    <Input
                      id="file"
                      type="file"
                      accept=".pdf"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="hidden" 
                    />
                    {uploadFile && (
                      <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 px-3 py-1 rounded-full mt-2">
                        <FileText className="h-4 w-4" />
                        {uploadFile.name}
                      </div>
                    )}
                  </div>
              </div>

            </CardContent>
             <CardFooter className="flex justify-between">
               <Button variant="outline" onClick={() => setStep(3)}>Skip for now</Button>
               <Button onClick={handleUploadRuleset} disabled={!uploadFile || isUploading}>
                 {isUploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                 Upload & Continue
               </Button>
            </CardFooter>
          </>
        )}

        {step === 3 && (
          <>
            <CardHeader>
              <CardTitle>NPC Recruited!</CardTitle>
              <CardDescription>Your NPC has been created successfully.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center justify-center space-y-4 py-8">
              <div className="rounded-full bg-green-500/15 p-3">
                <CheckCircle className="h-12 w-12 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold">{formData.gameName}</h3>
              <p className="text-sm text-muted-foreground text-center">
                 Ready to answer questions with NPC <strong>{formData.npcName}</strong> using {formData.persona} style.
              </p>
              {uploadFile && <p className="text-xs text-muted-foreground text-center">Includes knowledge from: {uploadFile.name}</p>}
            </CardContent>
            <CardFooter className="flex justify-center">
               <Button onClick={handleFinish} className="w-full sm:w-auto">Go to Ask Sessions</Button>
            </CardFooter>
          </>
        )}
      </Card>
    </div>
  );
}

function StepIndicator({ number, title, current, completed }: { number: number; title: string; current: boolean; completed: boolean }) {
  return (
    <div className="flex flex-col items-center space-y-1">
      <div
        className={`flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold transition-colors ${
          completed
            ? "bg-primary border-primary text-primary-foreground"
            : current
            ? "border-primary text-primary"
            : "border-muted text-muted-foreground"
        }`}
      >
        {completed ? <CheckCircle className="h-4 w-4" /> : number}
      </div>
      <span className={`text-xs ${current ? "font-medium text-foreground" : "text-muted-foreground"}`}>
        {title}
      </span>
    </div>
  );
}

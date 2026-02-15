import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FileText, ChevronRight } from "lucide-react";

interface CitationViewerProps {
  citation: {
    source: string;
    page: number | null;
    section: string | null;
    snippet: string;
    is_official: boolean;
  } | null;
  onClose: () => void;
}

export function CitationViewer({ citation, onClose }: CitationViewerProps) {
  if (!citation) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] border-l bg-background p-6 shadow-xl transition-transform duration-300 ease-in-out">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">Citation Details</h3>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-6">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground mb-1">Source</h4>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            <span className="font-medium">{citation.source}</span>
          </div>
          <div className="flex gap-2 mt-2">
             {citation.page && <Badge variant="outline">Page {citation.page}</Badge>}
             {citation.section && <Badge variant="secondary">{citation.section}</Badge>}
             {citation.is_official && <Badge className="bg-blue-600">Official</Badge>}
          </div>
        </div>

        <div>
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Context Snippet</h4>
          <Card className="bg-muted/50">
            <CardContent className="p-4 text-sm leading-relaxed whitespace-pre-wrap font-mono">
              {citation.snippet}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

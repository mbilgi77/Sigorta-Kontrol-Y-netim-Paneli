import { useState, useRef } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { UploadCloud, FileSpreadsheet } from "lucide-react";

export default function UploadDialog({ open, onOpenChange, onUploaded }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef();

  const submit = async () => {
    if (!file) { toast.error("Dosya seçin"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/records/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${data.inserted} kayıt yüklendi`);
      setFile(null);
      onUploaded?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Yükleme başarısız");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="upload-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl tracking-tight">Excel Yükle</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Beklenen sütunlar:</span> MARKA, MODEL, DONANIM, ŞASİ, RENK,
            DANIŞMAN, MÜŞTERİ, TRAFİK, KASKO, PSA KASKO, AÇIKLAMA. Değerler: ONAY / RED / X (—).
          </p>

          <div
            className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-muted/40 transition"
            onClick={() => inputRef.current?.click()}
            data-testid="upload-drop"
          >
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              data-testid="upload-file-input"
            />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileSpreadsheet className="h-8 w-8 text-emerald-600" />
                <div className="text-left">
                  <div className="font-medium text-sm">{file.name}</div>
                  <div className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground">
                <UploadCloud className="h-8 w-8 mx-auto mb-2" />
                <div className="text-sm">Dosya seçmek için tıklayın (.xlsx)</div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="upload-cancel">İptal</Button>
          <Button className="bg-slate-900 hover:bg-slate-800" onClick={submit} disabled={busy || !file} data-testid="upload-submit">
            {busy ? "Yükleniyor..." : "Yükle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

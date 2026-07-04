import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

const empty = {
  marka: "", model: "", donanim: "", sasi: "", renk: "",
  danisman: "", musteri: "",
  trafik: "YOK", kasko: "YOK", psa_kasko: "YOK",
  aciklama: "",
};

const STATUS_OPTIONS = [
  { value: "ONAY", label: "ONAY (Onaylandı)" },
  { value: "RED", label: "RED (Onaylanmadı)" },
  { value: "YOK", label: "— (Yok)" },
];

export default function RecordDialog({ open, onOpenChange, record, onSaved }) {
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const editing = !!record;

  useEffect(() => {
    if (open) {
      setForm(record ? { ...empty, ...record } : empty);
    }
  }, [open, record]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.marka.trim() || !form.danisman.trim()) {
      toast.error("Marka ve Danışman zorunlu");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form };
      delete payload.id;
      delete payload.created_at;
      if (editing) await api.put(`/records/${record.id}`, payload);
      else await api.post("/records", payload);
      toast.success(editing ? "Kayıt güncellendi" : "Kayıt eklendi");
      onSaved?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" data-testid="record-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl tracking-tight">
            {editing ? "Kaydı Düzenle" : "Yeni Kayıt"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="grid md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Marka *</Label>
            <Input value={form.marka} onChange={(e) => set("marka", e.target.value)} data-testid="input-marka" />
          </div>
          <div className="space-y-2">
            <Label>Model</Label>
            <Input value={form.model} onChange={(e) => set("model", e.target.value)} data-testid="input-model" />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Donanım</Label>
            <Input value={form.donanim} onChange={(e) => set("donanim", e.target.value)} data-testid="input-donanim" />
          </div>
          <div className="space-y-2">
            <Label>ŞASİ</Label>
            <Input value={form.sasi} onChange={(e) => set("sasi", e.target.value)} data-testid="input-sasi" />
          </div>
          <div className="space-y-2">
            <Label>Renk</Label>
            <Input value={form.renk} onChange={(e) => set("renk", e.target.value)} data-testid="input-renk" />
          </div>
          <div className="space-y-2">
            <Label>Danışman *</Label>
            <Input value={form.danisman} onChange={(e) => set("danisman", e.target.value)} data-testid="input-danisman" />
          </div>
          <div className="space-y-2">
            <Label>Müşteri</Label>
            <Input value={form.musteri} onChange={(e) => set("musteri", e.target.value)} data-testid="input-musteri" />
          </div>

          <div className="space-y-2">
            <Label>TRAFİK</Label>
            <Select value={form.trafik} onValueChange={(v) => set("trafik", v)}>
              <SelectTrigger data-testid="select-trafik"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>KASKO</Label>
            <Select value={form.kasko} onValueChange={(v) => set("kasko", v)}>
              <SelectTrigger data-testid="select-kasko"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>PSA KASKO</Label>
            <Select value={form.psa_kasko} onValueChange={(v) => set("psa_kasko", v)}>
              <SelectTrigger data-testid="select-psa-kasko"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label>Açıklama</Label>
            <Textarea rows={3} value={form.aciklama} onChange={(e) => set("aciklama", e.target.value)} data-testid="input-aciklama" />
          </div>

          <DialogFooter className="md:col-span-2 mt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="record-cancel">
              İptal
            </Button>
            <Button type="submit" className="bg-slate-900 hover:bg-slate-800" disabled={saving} data-testid="record-save">
              {saving ? "Kaydediliyor..." : editing ? "Güncelle" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

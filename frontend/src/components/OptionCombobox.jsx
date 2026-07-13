import { useState, useEffect, useMemo } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";

/**
 * Select-or-add combobox. Fetches /api/options/{kind} and lets user
 * pick an existing value or add a new one inline.
 */
export default function OptionCombobox({
  kind,        // "brands" | "donanims" | "consultants"
  value,
  onChange,
  placeholder = "Seçin...",
  testId,
  refreshKey,
}) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState([]);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/options/${kind}`);
      setOptions(data.values || []);
    } catch { /* noop */ }
  };

  useEffect(() => { load(); }, [kind, refreshKey]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.toLowerCase().includes(q));
  }, [options, query]);

  const canAdd = query.trim() && !options.some((o) => o.toLowerCase() === query.trim().toLowerCase());

  const addNew = async () => {
    const v = query.trim();
    if (!v) return;
    setAdding(true);
    try {
      await api.post(`/options/${kind}`, { value: v });
      await load();
      onChange(v);
      setQuery("");
      setOpen(false);
      toast.success("Eklendi");
    } catch (e) {
      toast.error("Eklenemedi");
    } finally {
      setAdding(false);
    }
  };

  const removeOption = async (v, e) => {
    e.stopPropagation();
    if (!window.confirm(`"${v}" listeden kaldırılsın mı?`)) return;
    try {
      await api.delete(`/options/${kind}/${encodeURIComponent(v)}`);
      await load();
      if (value === v) onChange("");
      toast.success("Kaldırıldı");
    } catch {
      toast.error("Kaldırılamadı");
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          className="w-full justify-between font-normal"
          data-testid={testId}
        >
          <span className={cn("truncate", !value && "text-muted-foreground")}>
            {value || placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <div className="p-2 border-b">
          <Input
            autoFocus
            placeholder="Ara veya yeni ekle..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-9"
            data-testid={`${testId}-search`}
          />
        </div>
        <div className="max-h-64 overflow-auto p-1">
          {filtered.length === 0 && !canAdd && (
            <div className="p-3 text-sm text-muted-foreground text-center">Seçenek yok</div>
          )}
          {filtered.map((o) => (
            <div
              key={o}
              onClick={() => { onChange(o); setOpen(false); setQuery(""); }}
              className={cn(
                "group flex items-center justify-between gap-2 px-2 py-1.5 rounded-sm text-sm cursor-pointer hover:bg-accent",
                value === o && "bg-accent",
              )}
              data-testid={`${testId}-item-${o}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <Check className={cn("h-4 w-4 shrink-0", value === o ? "opacity-100" : "opacity-0")} />
                <span className="truncate">{o}</span>
              </div>
              <button
                type="button"
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-rose-600"
                onClick={(e) => removeOption(o, e)}
                title="Listeden kaldır"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}

          {canAdd && (
            <button
              type="button"
              onClick={addNew}
              disabled={adding}
              className="w-full flex items-center gap-2 px-2 py-2 mt-1 border-t text-sm text-blue-600 hover:bg-accent rounded-sm"
              data-testid={`${testId}-add-new`}
            >
              <Plus className="h-4 w-4" />
              <span>&quot;{query.trim()}&quot; ekle</span>
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

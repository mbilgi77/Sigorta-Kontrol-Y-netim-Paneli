import { useEffect, useMemo, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { toast, Toaster } from "sonner";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  ShieldCheck, LogOut, Upload, Plus, Search, Pencil, Trash2, Filter,
  TrendingUp, XCircle, CheckCircle2, LayoutDashboard, FileSpreadsheet, FileText,
} from "lucide-react";
import RecordDialog from "@/components/RecordDialog";
import UploadDialog from "@/components/UploadDialog";

const MONTHS = [
  "Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
  "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık",
];

const CHART_COLORS = ["#0f172a","#2563eb","#059669","#d97706","#e11d48","#7c3aed","#0891b2","#65a30d"];

function StatBadge({ v }) {
  if (v === "ONAY") return <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-200 hover:bg-emerald-100" data-testid={`status-onay`}>ONAY</Badge>;
  if (v === "RED") return <Badge className="bg-rose-100 text-rose-800 border border-rose-200 hover:bg-rose-100" data-testid={`status-red`}>RED</Badge>;
  return <Badge variant="outline" className="text-muted-foreground" data-testid={`status-yok`}>—</Badge>;
}

function KpiCard({ label, value, sub, tone = "default", testId }) {
  const tones = {
    default: "text-slate-900",
    approved: "text-emerald-600",
    unapproved: "text-rose-600",
    accent: "text-blue-600",
  };
  return (
    <Card className="p-6 border-border" data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className={`mt-3 font-num text-4xl font-semibold ${tones[tone]}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-2">{sub}</div>}
    </Card>
  );
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(String(now.getFullYear()));
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [statsData, setStatsData] = useState(null);
  const [records, setRecords] = useState([]);
  const [filters, setFilters] = useState({ markalar: [], danismanlar: [] });
  const [fMarka, setFMarka] = useState("__all__");
  const [fDanisman, setFDanisman] = useState("__all__");
  const [fDurum, setFDurum] = useState("__all__");
  const [search, setSearch] = useState("");
  const [editRec, setEditRec] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [openUpload, setOpenUpload] = useState(false);

  const years = useMemo(() => {
    const y = now.getFullYear();
    return [String(y - 1), String(y), String(y + 1)];
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const params = {};
      if (year !== "__all__") params.year = year;
      if (month !== "__all__") params.month = month;

      const [s, r, f] = await Promise.all([
        api.get("/stats", { params }),
        api.get("/records", {
          params: {
            ...params,
            ...(fMarka !== "__all__" ? { marka: fMarka } : {}),
            ...(fDanisman !== "__all__" ? { danisman: fDanisman } : {}),
            ...(fDurum !== "__all__" ? { durum: fDurum } : {}),
          },
        }),
        api.get("/filters"),
      ]);
      setStatsData(s.data);
      setRecords(r.data);
      setFilters(f.data);
    } catch (e) {
      toast.error("Veri yüklenemedi");
    }
  }, [year, month, fMarka, fDanisman, fDurum]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const filteredRecords = useMemo(() => {
    if (!search.trim()) return records;
    const q = search.toLowerCase();
    return records.filter((r) =>
      [r.marka, r.model, r.sasi, r.musteri, r.danisman]
        .join(" ").toLowerCase().includes(q)
    );
  }, [records, search]);

  const handleDelete = async (id) => {
    if (!window.confirm("Bu kaydı silmek istediğinizden emin misiniz?")) return;
    try {
      await api.delete(`/records/${id}`);
      toast.success("Kayıt silindi");
      loadAll();
    } catch { toast.error("Silinemedi"); }
  };

  const buildExportParams = () => {
    const p = new URLSearchParams();
    if (year !== "__all__") p.set("year", year);
    if (month !== "__all__") p.set("month", month);
    if (fMarka !== "__all__") p.set("marka", fMarka);
    if (fDanisman !== "__all__") p.set("danisman", fDanisman);
    if (fDurum !== "__all__") p.set("durum", fDurum);
    return p.toString();
  };

  const downloadBlob = async (path, ext) => {
    try {
      const res = await api.get(path, { responseType: "blob" });
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sigorta-kayitlar-${new Date().toISOString().slice(0,10)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("İndirildi");
    } catch {
      toast.error("İndirme başarısız");
    }
  };

  const exportExcel = () => {
    const q = buildExportParams();
    downloadBlob(`/export/excel${q ? `?${q}` : ""}`, "xlsx");
  };
  const exportPdf = () => {
    const q = buildExportParams();
    downloadBlob(`/export/pdf${q ? `?${q}` : ""}`, "pdf");
  };

  const openAdd = () => { setEditRec(null); setOpenDialog(true); };
  const openEdit = (r) => { setEditRec(r); setOpenDialog(true); };

  const monthLabel = month === "__all__" ? "Tüm Aylar" : MONTHS[Number(month) - 1];
  const yearLabel = year === "__all__" ? "Tüm Yıllar" : year;

  return (
    <div className="min-h-screen bg-background">
      <Toaster richColors position="top-right" />

      {/* Top bar */}
      <header className="border-b bg-white sticky top-0 z-20">
        <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-md bg-slate-900 grid place-items-center text-white">
              <ShieldCheck className="h-4.5 w-4.5" />
            </div>
            <div>
              <div className="font-heading font-bold text-lg tracking-tight leading-none">Sigorta Kontrol</div>
              <div className="text-[11px] text-muted-foreground mt-1">Yönetim Paneli</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground hidden sm:block" data-testid="user-email">{user?.email}</span>
            <Button variant="outline" size="sm" onClick={logout} data-testid="logout-button">
              <LogOut className="h-4 w-4 mr-2" /> Çıkış
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-8 space-y-8" data-testid="dashboard-main">
        {/* Header row */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-widest">
              <LayoutDashboard className="h-3.5 w-3.5" /> Gösterge Paneli
            </div>
            <h1 className="font-heading text-4xl md:text-5xl font-bold tracking-tight mt-2">
              {monthLabel} <span className="text-muted-foreground">/ {yearLabel}</span>
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Select value={year} onValueChange={setYear}>
              <SelectTrigger className="w-[130px]" data-testid="year-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tüm Yıllar</SelectItem>
                {years.map((y) => <SelectItem key={y} value={y}>{y}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={month} onValueChange={setMonth}>
              <SelectTrigger className="w-[140px]" data-testid="month-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tüm Aylar</SelectItem>
                {MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={exportExcel} data-testid="export-excel-button">
              <FileSpreadsheet className="h-4 w-4 mr-2" /> Excel İndir
            </Button>
            <Button variant="outline" onClick={exportPdf} data-testid="export-pdf-button">
              <FileText className="h-4 w-4 mr-2" /> PDF İndir
            </Button>
            <Button variant="outline" onClick={() => setOpenUpload(true)} data-testid="upload-button">
              <Upload className="h-4 w-4 mr-2" /> Excel Yükle
            </Button>
            <Button className="bg-slate-900 hover:bg-slate-800" onClick={openAdd} data-testid="add-record-button">
              <Plus className="h-4 w-4 mr-2" /> Yeni Kayıt
            </Button>
          </div>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4" data-testid="kpi-grid">
          <KpiCard label="Toplam Kayıt" value={statsData?.total ?? 0} sub="Filtrelenmiş" testId="kpi-total" />
          <KpiCard label="TRAFİK Onay" value={statsData?.trafik_onay ?? 0} tone="approved" testId="kpi-trafik" />
          <KpiCard label="KASKO Onay" value={statsData?.kasko_onay ?? 0} tone="approved" testId="kpi-kasko" />
          <KpiCard label="PSA KASKO Onay" value={statsData?.psa_kasko_onay ?? 0} tone="approved" testId="kpi-psa" />
          <KpiCard label="Onaylanmayan" value={statsData?.unapproved_count ?? 0} tone="unapproved" testId="kpi-unapproved" />
        </div>

        {/* Charts */}
        <div className="grid lg:grid-cols-5 gap-4">
          <Card className="p-6 lg:col-span-3" data-testid="chart-brand-totals">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-widest text-muted-foreground">Marka Bazlı Toplam</div>
                <h3 className="font-heading text-xl font-bold mt-1">Tüm teklifler</h3>
              </div>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="mt-6 h-[280px]">
              <ResponsiveContainer>
                <BarChart data={statsData?.brand_totals ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="marka" tick={{ fontSize: 12 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#64748b" allowDecimals={false} />
                  <Tooltip cursor={{ fill: "rgba(15,23,42,0.05)" }} />
                  <Bar dataKey="adet" fill="#0f172a" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-6 lg:col-span-2" data-testid="chart-unapproved">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-widest text-muted-foreground">Onaylanmayan</div>
                <h3 className="font-heading text-xl font-bold mt-1">Marka Dağılımı</h3>
              </div>
              <XCircle className="h-4 w-4 text-rose-600" />
            </div>
            <div className="mt-6 h-[280px]">
              {(statsData?.brand_unapproved?.length ?? 0) === 0 ? (
                <div className="h-full grid place-items-center text-sm text-muted-foreground">
                  <div className="text-center">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                    Onaylanmayan teklif bulunmuyor.
                  </div>
                </div>
              ) : (
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={statsData?.brand_unapproved ?? []}
                      dataKey="adet"
                      nameKey="marka"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={95}
                      paddingAngle={2}
                    >
                      {(statsData?.brand_unapproved ?? []).map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </Card>
        </div>

        {/* Consultant table */}
        <Card className="p-0 overflow-hidden" data-testid="consultants-card">
          <div className="p-6 flex items-center justify-between border-b">
            <div>
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Danışman Performansı</div>
              <h3 className="font-heading text-xl font-bold mt-1">Aylık Onay Adetleri</h3>
            </div>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Danışman</TableHead>
                  <TableHead className="text-right">TRAFİK Onay</TableHead>
                  <TableHead className="text-right">KASKO Onay</TableHead>
                  <TableHead className="text-right">PSA KASKO Onay</TableHead>
                  <TableHead className="text-right">Red Toplam</TableHead>
                  <TableHead className="text-right">Toplam</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(statsData?.consultants ?? []).length === 0 && (
                  <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">Kayıt yok</TableCell></TableRow>
                )}
                {(statsData?.consultants ?? []).map((c) => (
                  <TableRow key={c.danisman} data-testid={`consultant-row-${c.danisman}`}>
                    <TableCell className="font-medium">{c.danisman}</TableCell>
                    <TableCell className="text-right font-num">{c.trafik_onay}</TableCell>
                    <TableCell className="text-right font-num">{c.kasko_onay}</TableCell>
                    <TableCell className="text-right font-num">{c.psa_kasko_onay}</TableCell>
                    <TableCell className="text-right font-num text-rose-600">
                      {c.trafik_red + c.kasko_red + c.psa_kasko_red}
                    </TableCell>
                    <TableCell className="text-right font-num font-semibold">{c.toplam}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>

        {/* Records table */}
        <Card className="p-0 overflow-hidden" data-testid="records-card">
          <div className="p-6 border-b space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-widest text-muted-foreground">Kayıtlar</div>
                <h3 className="font-heading text-xl font-bold mt-1">Detaylı Liste</h3>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Filter className="h-3.5 w-3.5" />
                {filteredRecords.length} kayıt
              </div>
            </div>
            <div className="grid md:grid-cols-4 gap-3">
              <div className="relative">
                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Ara: marka, model, şasi, müşteri..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  data-testid="records-search"
                />
              </div>
              <Select value={fMarka} onValueChange={setFMarka}>
                <SelectTrigger data-testid="filter-marka"><SelectValue placeholder="Marka" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tüm Markalar</SelectItem>
                  {filters.markalar.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={fDanisman} onValueChange={setFDanisman}>
                <SelectTrigger data-testid="filter-danisman"><SelectValue placeholder="Danışman" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tüm Danışmanlar</SelectItem>
                  {filters.danismanlar.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={fDurum} onValueChange={setFDurum}>
                <SelectTrigger data-testid="filter-durum"><SelectValue placeholder="Durum" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tüm Durumlar</SelectItem>
                  <SelectItem value="ONAY">ONAY</SelectItem>
                  <SelectItem value="RED">RED</SelectItem>
                  <SelectItem value="YOK">—</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Marka / Model</TableHead>
                  <TableHead>Danışman</TableHead>
                  <TableHead>Müşteri</TableHead>
                  <TableHead>ŞASİ</TableHead>
                  <TableHead>TRAFİK</TableHead>
                  <TableHead>KASKO</TableHead>
                  <TableHead>PSA KASKO</TableHead>
                  <TableHead className="w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRecords.length === 0 && (
                  <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">Kayıt bulunmuyor</TableCell></TableRow>
                )}
                {filteredRecords.map((r) => (
                  <TableRow key={r.id} data-testid={`record-row-${r.id}`}>
                    <TableCell>
                      <div className="font-medium">{r.marka} {r.model}</div>
                      <div className="text-xs text-muted-foreground">{r.donanim}</div>
                    </TableCell>
                    <TableCell>{r.danisman}</TableCell>
                    <TableCell>{r.musteri}</TableCell>
                    <TableCell className="font-mono text-xs">{r.sasi}</TableCell>
                    <TableCell><StatBadge v={r.trafik} /></TableCell>
                    <TableCell><StatBadge v={r.kasko} /></TableCell>
                    <TableCell><StatBadge v={r.psa_kasko} /></TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(r)} data-testid={`edit-record-${r.id}`}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(r.id)} data-testid={`delete-record-${r.id}`}>
                          <Trash2 className="h-4 w-4 text-rose-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      </main>

      <RecordDialog
        open={openDialog}
        onOpenChange={setOpenDialog}
        record={editRec}
        onSaved={() => { setOpenDialog(false); loadAll(); }}
      />
      <UploadDialog
        open={openUpload}
        onOpenChange={setOpenUpload}
        onUploaded={() => { setOpenUpload(false); loadAll(); }}
      />
    </div>
  );
}

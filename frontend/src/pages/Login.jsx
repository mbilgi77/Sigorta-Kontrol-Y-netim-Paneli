import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { ShieldCheck, LogIn } from "lucide-react";

export default function Login() {
  const { user, ready, login } = useAuth();
  const [email, setEmail] = useState("admin@sigorta.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  if (!ready) return null;
  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email, password);
      nav("/");
    } catch (e) {
      setErr(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      <div
        className="hidden lg:block relative bg-cover bg-center"
        style={{
          backgroundImage:
            "linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(15,23,42,0.55) 100%), url('https://images.unsplash.com/photo-1644749700856-a82a92828a1b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzV8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBjYXIlMjBzaG93cm9vbSUyMGludGVyaW9yJTIwYXJjaGl0ZWN0dXJlfGVufDB8fHx8MTc4MjUzNzAxNXww&ixlib=rb-4.1.0&q=85')",
        }}
      >
        <div className="absolute inset-0 flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-md bg-white/10 backdrop-blur border border-white/20 grid place-items-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="font-heading text-lg font-bold tracking-tight">Sigorta Kontrol</span>
          </div>
          <div>
            <h1 className="font-heading text-5xl xl:text-6xl font-bold leading-[1.02] tracking-tight">
              Danışman Performans
              <br />
              & Sigorta Onay
              <br />
              <span className="text-white/60">Kontrol Paneli</span>
            </h1>
            <p className="mt-6 text-white/70 max-w-md">
              Aylık TRAFİK, KASKO ve PSA KASKO adetlerini, onaylanmayan teklifleri ve marka
              dağılımlarını tek bir yerden yönetin.
            </p>
          </div>
          <div className="text-xs text-white/40 font-mono">v1.0 · Yönetici Paneli</div>
        </div>
      </div>

      <div className="flex items-center justify-center p-6 lg:p-16">
        <form onSubmit={submit} className="w-full max-w-sm space-y-6" data-testid="login-form">
          <div>
            <h2 className="font-heading text-3xl font-bold tracking-tight">Yönetici Girişi</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Kontrol paneline erişmek için giriş yapın.
            </p>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">E-posta</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Şifre</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="login-password-input"
              />
            </div>
          </div>

          {err && (
            <div
              className="text-sm text-brand-unapproved bg-rose-50 border border-rose-200 rounded-md p-3"
              data-testid="login-error"
            >
              {err}
            </div>
          )}

          <Button
            type="submit"
            className="w-full h-11 bg-slate-900 hover:bg-slate-800"
            disabled={loading}
            data-testid="login-submit-button"
          >
            <LogIn className="h-4 w-4 mr-2" />
            {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
          </Button>

          <div className="text-xs text-muted-foreground text-center">
            Varsayılan: <span className="font-mono">admin@sigorta.com</span> /{" "}
            <span className="font-mono">admin123</span>
          </div>
        </form>
      </div>
    </div>
  );
}

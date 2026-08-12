import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught UI render error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleResetSession = () => {
    try {
      localStorage.removeItem('readomni_app_session_v1');
      sessionStorage.clear();
    } catch { /* ignore */ }
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center p-6 bg-[var(--background)] text-[var(--foreground)] text-center select-none">
          <div className="max-w-md w-full p-8 rounded-3xl border border-[var(--border)] bg-[var(--card)] shadow-2xl space-y-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-16 h-16 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center mx-auto shadow-inner">
              <AlertTriangle size={32} />
            </div>

            <div className="space-y-2">
              <h2 className="text-xl font-bold tracking-tight">Terjadi Kesalahan Tampilan</h2>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Aplikasi mengalami kendala saat memuat elemen antarmuka. Anda dapat me-refresh atau mereset sesi untuk kembali ke halaman utama.
              </p>
            </div>

            {this.state.error && (
              <div className="p-3 rounded-xl bg-destructive/5 border border-destructive/20 text-left font-mono text-[11px] text-destructive/90 overflow-auto max-h-32">
                {this.state.error.message || String(this.state.error)}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button 
                onClick={this.handleReload} 
                variant="outline" 
                className="flex-1 rounded-xl gap-2 font-bold text-xs h-11"
              >
                <RefreshCw size={14} />
                Muat Ulang
              </Button>
              <Button 
                onClick={this.handleResetSession} 
                className="flex-1 rounded-xl gap-2 font-bold text-xs h-11 bg-[var(--primary)] text-[var(--primary-foreground)]"
              >
                <Home size={14} />
                Kembali ke Beranda
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

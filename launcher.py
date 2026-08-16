"""
ReadOmni AI — Modern CLI Launcher
Inspired by Claude Code, Vite, and Next.js dev server aesthetics.
"""

import sys
import os
import time
import socket
import subprocess
import threading
import webbrowser

# ─── Platform Init ───────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        os.system("color")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# ─── ANSI Colors & Styles ───────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ULINE   = "\033[4m"

# Refined palette — muted, professional tones
TEAL    = "\033[38;2;94;234;212m"   # Primary accent
BLUE    = "\033[38;2;96;165;250m"   # Links, info
INDIGO  = "\033[38;2;129;140;248m"  # Highlights
AMBER   = "\033[38;2;251;191;36m"   # Warnings, pending
RED     = "\033[38;2;248;113;113m"  # Errors, destructive
WHITE   = "\033[38;2;248;250;252m"  # Primary text
GRAY    = "\033[38;2;148;163;184m"  # Secondary text
FAINT   = "\033[38;2;100;116;139m"  # Tertiary / timestamps
SLATE   = "\033[38;2;71;85;105m"    # Borders, dividers

# ─── Configuration ───────────────────────────────────────────────────────────
VERSION       = "2.0"
ROOT_DIR      = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR   = os.path.join(ROOT_DIR, "backend")
BACKEND_PORT  = 8000
FRONTEND_PORT = 5173

# ─── State ───────────────────────────────────────────────────────────────────
backend_proc  = None
frontend_proc = None
running       = True
print_lock    = threading.Lock()
_startup_time = time.time()


# ═══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

def open_url(url: str):
    """Reliable URL opener for Windows and other OS."""
    try:
        if sys.platform == "win32":
            os.startfile(url)
        else:
            webbrowser.open(url)
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            pass

def uptime_str() -> str:
    elapsed = int(time.time() - _startup_time)
    if elapsed < 60:
        return f"{elapsed}s"
    m, s = divmod(elapsed, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


# ═══════════════════════════════════════════════════════════════════════════════
#  Logging
# ═══════════════════════════════════════════════════════════════════════════════

def log(prefix: str, msg: str, color: str = GRAY):
    """Clean, timestamped log output."""
    clean = msg.strip()
    if not clean:
        return
    ts = time.strftime("%H:%M:%S")
    with print_lock:
        sys.stdout.write(f"  {FAINT}{ts}{RESET}  {color}{prefix:<10}{RESET} {DIM}{clean}{RESET}\n")
        sys.stdout.flush()

def log_reader(proc, prefix, color):
    """Read subprocess stdout line by line and log it."""
    try:
        for line in iter(proc.stdout.readline, ''):
            if not running or not line:
                break
            log(prefix, line, color)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  Banner — The Hero Display
# ═══════════════════════════════════════════════════════════════════════════════

def status_dot(online: bool, label: str, port: int) -> str:
    if online:
        return f"  {TEAL}●{RESET}  {WHITE}{label}{RESET} {FAINT}:{port}{RESET}"
    return f"  {AMBER}○{RESET}  {GRAY}{label}{RESET} {FAINT}:{port} starting...{RESET}"

def print_banner():
    with print_lock:
        os.system("cls" if sys.platform == "win32" else "clear")

        hostname = socket.gethostname()
        local_ip = get_local_ip()
        b_ok = check_port(BACKEND_PORT)
        f_ok = check_port(FRONTEND_PORT)

        # ── Header
        sys.stdout.write(f"""
  {TEAL}{BOLD}ReadOmni AI{RESET}  {FAINT}v{VERSION}{RESET}
  {FAINT}Self-hosted AI novel translator & reader{RESET}

""")

        # ── Services
        sys.stdout.write(f"  {SLATE}{'─' * 56}{RESET}\n")
        sys.stdout.write(f"  {DIM}{WHITE}Services{RESET}\n\n")
        sys.stdout.write(status_dot(b_ok, "Backend", BACKEND_PORT) + f"    {FAINT}FastAPI + Uvicorn{RESET}\n")
        sys.stdout.write(status_dot(f_ok, "Frontend", FRONTEND_PORT) + f"   {FAINT}Vite + React 19{RESET}\n")
        sys.stdout.write(f"\n  {SLATE}{'─' * 56}{RESET}\n")

        # ── Access URLs
        sys.stdout.write(f"  {DIM}{WHITE}Access{RESET}\n\n")
        sys.stdout.write(f"  {TEAL}➜{RESET}  {WHITE}Local Laptop{RESET}     {ULINE}http://localhost:{FRONTEND_PORT}{RESET}\n")
        sys.stdout.write(f"  {BLUE}➜{RESET}  {WHITE}Mobile (WiFi){RESET}    {ULINE}{BLUE}http://{hostname}.local:{FRONTEND_PORT}{RESET}\n")
        sys.stdout.write(f"  {INDIGO}➜{RESET}  {GRAY}Network IP{RESET}       {FAINT}{ULINE}http://{local_ip}:{FRONTEND_PORT}{RESET}\n")
        sys.stdout.write(f"  {FAINT}➜  Swagger API      http://localhost:{BACKEND_PORT}/docs{RESET}\n")
        sys.stdout.write(f"\n  {SLATE}{'─' * 56}{RESET}\n")

        # ── Shortcuts
        sys.stdout.write(f"  {DIM}{WHITE}Shortcuts (Tekan tombol keyboard):{RESET}\n\n")
        sys.stdout.write(f"  {WHITE}[1]{RESET} Buka Browser     {WHITE}[3]{RESET} Restart Backend    {WHITE}[5]{RESET} Buka Folder\n")
        sys.stdout.write(f"  {WHITE}[2]{RESET} Swagger Docs     {WHITE}[4]{RESET} Restart Frontend   {WHITE}[s]{RESET} Cek Status\n")
        sys.stdout.write(f"  {WHITE}[c]{RESET} Bersihkan Layar  {RED}[q]{RESET} Matikan & Keluar\n")
        sys.stdout.write(f"\n  {SLATE}{'─' * 56}{RESET}\n")

        # ── Log header
        sys.stdout.write(f"  {DIM}{WHITE}Live Logs{RESET}\n\n")
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════════
#  Process Management
# ═══════════════════════════════════════════════════════════════════════════════

def start_backend():
    global backend_proc
    if backend_proc and backend_proc.poll() is None:
        return
    log("backend", "Memulai FastAPI server...", TEAL)

    cmd = [sys.executable, "-u", "-m", "uvicorn", "main:app",
           "--reload", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    backend_proc = subprocess.Popen(
        cmd, cwd=BACKEND_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, text=True, bufsize=1, encoding='utf-8', errors='replace'
    )
    t = threading.Thread(target=log_reader, args=(backend_proc, "backend", TEAL), daemon=True)
    t.start()


def start_frontend():
    global frontend_proc
    if frontend_proc and frontend_proc.poll() is None:
        return
    log("frontend", "Memulai Vite dev server...", BLUE)

    cmd = ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev"]
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"

    frontend_proc = subprocess.Popen(
        cmd, cwd=ROOT_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, text=True, bufsize=1, encoding='utf-8', errors='replace'
    )
    t = threading.Thread(target=log_reader, args=(frontend_proc, "frontend", BLUE), daemon=True)
    t.start()


def stop_process(proc, name: str):
    """Gracefully stop a subprocess tree."""
    if not proc:
        return
    log(name, "Menghentikan proses...", AMBER)
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        pass


def stop_backend():
    global backend_proc
    stop_process(backend_proc, "backend")
    backend_proc = None

def stop_frontend():
    global frontend_proc
    stop_process(frontend_proc, "frontend")
    frontend_proc = None


def print_status():
    b_ok = check_port(BACKEND_PORT)
    f_ok = check_port(FRONTEND_PORT)
    b_dot = f"{TEAL}●{RESET}" if b_ok else f"{RED}●{RESET}"
    f_dot = f"{TEAL}●{RESET}" if f_ok else f"{RED}●{RESET}"
    b_lbl = f"{WHITE}online{RESET}" if b_ok else f"{RED}offline{RESET}"
    f_lbl = f"{WHITE}online{RESET}" if f_ok else f"{RED}offline{RESET}"
    log("status", f"{b_dot} Backend {b_lbl}  {f_dot} Frontend {f_lbl}  {FAINT}uptime {uptime_str()}{RESET}", INDIGO)


def ensure_firewall_rules():
    """Check/create Windows Firewall inbound rules in background."""
    if sys.platform != "win32":
        return

    rules = [
        ("ReadOmni AI - Frontend (Vite)", FRONTEND_PORT),
        ("ReadOmni AI - Backend (FastAPI)", BACKEND_PORT),
    ]

    for rule_name, port in rules:
        try:
            check = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if check.returncode == 0:
                continue

            subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule_name}", "dir=in", "action=allow", "protocol=TCP",
                 f"localport={port}", "profile=private,domain"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


def wait_for_services(timeout: float = 15.0):
    """Poll ports until both services are online, then refresh banner."""
    start = time.time()
    while time.time() - start < timeout:
        if check_port(BACKEND_PORT) and check_port(FRONTEND_PORT):
            break
        time.sleep(0.5)
    print_banner()
    log("ready", f"Semua layanan online dalam {time.time() - start:.1f}s", TEAL)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Loop & Hotkey Handler
# ═══════════════════════════════════════════════════════════════════════════════

def handle_key(ch: str) -> bool:
    """Process a single hotkey character. Returns False if quit requested."""
    ch = ch.lower().strip()
    if not ch:
        return True

    if ch == '1':
        log("action", f"🌐 Membuka browser: http://localhost:{FRONTEND_PORT}", TEAL)
        open_url(f"http://localhost:{FRONTEND_PORT}")
    elif ch == '2':
        log("action", f"📑 Membuka API docs: http://localhost:{BACKEND_PORT}/docs", BLUE)
        open_url(f"http://localhost:{BACKEND_PORT}/docs")
    elif ch == '3':
        log("action", "🔄 Merestart Backend FastAPI...", AMBER)
        stop_backend()
        time.sleep(0.5)
        start_backend()
    elif ch == '4':
        log("action", "🔄 Merestart Frontend Vite...", AMBER)
        stop_frontend()
        time.sleep(0.5)
        start_frontend()
    elif ch == '5':
        log("action", "📁 Membuka folder project...", BLUE)
        if sys.platform == "win32":
            os.startfile(ROOT_DIR)
        else:
            subprocess.Popen(["xdg-open", ROOT_DIR])
    elif ch == 'c':
        print_banner()
    elif ch == 's':
        print_status()
    elif ch in ['q', '\x03']:  # q or Ctrl+C
        return False
    return True


def main():
    global running
    print_banner()

    # Background firewall check
    threading.Thread(target=ensure_firewall_rules, daemon=True).start()

    start_backend()
    start_frontend()

    # Auto-refresh banner when services come online
    threading.Thread(target=wait_for_services, daemon=True).start()

    try:
        while running:
            if HAS_MSVCRT:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    # Handle extended keys (arrow keys, function keys, numpad)
                    if ch in ('\x00', '\xe0'):
                        ch2 = msvcrt.getwch()
                        numpad_map = {'O': '1', 'P': '2', 'Q': '3', 'K': '4', 'M': '6', 'G': '7', 'H': '8', 'I': '9'}
                        ch = numpad_map.get(ch2, '')

                    if not handle_key(ch):
                        break
                time.sleep(0.05)
            else:
                try:
                    cmd = input().strip().lower()
                    if not handle_key(cmd):
                        break
                except (KeyboardInterrupt, EOFError):
                    break
    finally:
        running = False
        sys.stdout.write(f"\n  {AMBER}Menutup semua layanan background...{RESET}\n")
        sys.stdout.flush()
        stop_backend()
        stop_frontend()
        sys.stdout.write(f"  {TEAL}✓{RESET} {WHITE}Semua layanan berhasil dimatikan dengan bersih. Sampai jumpa!{RESET}\n\n")
        sys.stdout.flush()
        time.sleep(0.5)


if __name__ == "__main__":
    main()

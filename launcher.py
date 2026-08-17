"""
Translator Web — Control Hub Launcher
Clean, modern CLI launcher and pre-flight diagnostics.
"""

import sys
import os
import time
import socket
import subprocess
import threading
import webbrowser
import re
import argparse
import shutil

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
APP_NAME      = "Translator Web"
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
    """
    Select active physical Wi-Fi/Ethernet LAN IPv4 address.
    Filters out loopback, APIPA, Cloudflare WARP, VPN/tunnel, virtual,
    Docker, WSL, Hyper-V, and Bluetooth adapters by adapter identity.
    Does not exclude valid physical LANs on 172.16.0.0/12.
    """
    if sys.platform == "win32":
        try:
            res = subprocess.run(["ipconfig"], capture_output=True, text=True, errors="replace", timeout=2)
            adapters = []
            current = None
            for line in res.stdout.splitlines():
                line = line.rstrip()
                if not line:
                    continue
                if not line.startswith(" ") and ":" in line:
                    name = line.split("adapter ", 1)[-1].rstrip(":") if "adapter " in line else line.rstrip(":")
                    current = {"name": name, "ip": None, "disconnected": False}
                    adapters.append(current)
                elif current:
                    if "Media disconnected" in line or "Media State" in line:
                        current["disconnected"] = True
                    elif "IPv4 Address" in line or "IPv4" in line:
                        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
                        if m:
                            current["ip"] = m.group(1)

            excluded_keywords = (
                "warp", "cloudflare", "vpn", "tunnel", "tap", "tun", "wireguard",
                "wsl", "vethernet", "virtualbox", "vmware", "docker", "hyper-v",
                "bluetooth", "tailscale", "zerotier", "pseudo"
            )

            physical_candidates = []
            other_candidates = []
            for ad in adapters:
                if ad.get("disconnected") or not ad.get("ip"):
                    continue
                ip = ad["ip"]
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue

                ad_name_lower = ad["name"].lower()
                if any(kw in ad_name_lower for kw in excluded_keywords):
                    continue

                if any(kw in ad_name_lower for kw in ("wi-fi", "wireless", "wlan", "ethernet", "lan")):
                    physical_candidates.append(ip)
                else:
                    other_candidates.append(ip)

            if physical_candidates:
                return physical_candidates[0]
            if other_candidates:
                return other_candidates[0]
        except Exception:
            pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            probe_ip = s.getsockname()[0]
            if not probe_ip.startswith("127.") and not probe_ip.startswith("169.254."):
                return probe_ip
    except Exception:
        pass

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
  {TEAL}{BOLD}{APP_NAME}{RESET}  {FAINT}v{VERSION}{RESET}
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
        (f"{APP_NAME} - Frontend (Vite)", FRONTEND_PORT),
        (f"{APP_NAME} - Backend (FastAPI)", BACKEND_PORT),
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


def wait_for_services(timeout: float = 15.0, open_browser: bool = False):
    """Poll ports until both services are online, then refresh banner."""
    start = time.time()
    while time.time() - start < timeout:
        if check_port(BACKEND_PORT) and check_port(FRONTEND_PORT):
            break
        time.sleep(0.5)
    print_banner()
    log("ready", f"Semua layanan online dalam {time.time() - start:.1f}s", TEAL)
    if open_browser:
        open_url(f"http://localhost:{FRONTEND_PORT}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Diagnostics (Doctor)
# ═══════════════════════════════════════════════════════════════════════════════

def run_doctor() -> int:
    """
    Perform read-only environment and pre-flight diagnostics.
    Result categories: PASS, WARN, FAIL, SKIP.
    Never creates, migrates, writes, or mutates any database or files.
    Returns 0 if no FAIL items, 1 if any FAIL item occurs.
    """
    sys.stdout.write(f"\n  {TEAL}{BOLD}{APP_NAME} — Environment Doctor{RESET}\n")
    sys.stdout.write(f"  {FAINT}Read-only system & pre-flight diagnostics{RESET}\n\n")
    sys.stdout.write(f"  {SLATE}{'─' * 60}{RESET}\n")

    results = []

    def record(category: str, title: str, details: str = ""):
        results.append(category)
        if category == "PASS":
            cat_badge = f"{TEAL}[PASS]{RESET}"
        elif category == "WARN":
            cat_badge = f"{AMBER}[WARN]{RESET}"
        elif category == "FAIL":
            cat_badge = f"{RED}[FAIL]{RESET}"
        else:
            cat_badge = f"{GRAY}[SKIP]{RESET}"
        sys.stdout.write(f"  {cat_badge} {WHITE}{title}{RESET}\n")
        if details:
            sys.stdout.write(f"         {FAINT}{details}{RESET}\n")

    # 1. Python Runtime
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 11):
        record("PASS", f"Python Runtime: v{py_str}", f"Executable: {sys.executable}")
    else:
        record("FAIL", f"Python Runtime: v{py_str}", "Python 3.11+ is required.")

    # 2. Node.js & npm
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if node_bin:
        try:
            node_ver = subprocess.run([node_bin, "-v"], capture_output=True, text=True, timeout=2).stdout.strip()
            record("PASS", f"Node.js Runtime: {node_ver}", f"Binary: {node_bin}")
        except Exception:
            record("PASS", "Node.js Runtime found", f"Binary: {node_bin}")
    else:
        record("FAIL", "Node.js Runtime missing", "Node.js v20+ is required to build/run the Vite frontend.")

    if npm_bin:
        try:
            npm_ver = subprocess.run([npm_bin, "-v"], capture_output=True, text=True, timeout=2).stdout.strip()
            record("PASS", f"Package Manager: npm v{npm_ver}", f"Binary: {npm_bin}")
        except Exception:
            record("PASS", "Package Manager: npm found", f"Binary: {npm_bin}")
    else:
        record("FAIL", "npm missing", "npm is required to run the frontend.")

    # 3. Project Directory Structure
    req_paths = [
        ("Backend Entry", os.path.join(BACKEND_DIR, "main.py")),
        ("Frontend Config", os.path.join(ROOT_DIR, "package.json")),
        ("Vite Config", os.path.join(ROOT_DIR, "vite.config.ts")),
        ("Uploads Directory", os.path.join(BACKEND_DIR, "uploads", "images")),
    ]
    all_paths_ok = True
    for label, p in req_paths:
        if not os.path.exists(p):
            all_paths_ok = False
            record("FAIL", f"Missing Project File: {label}", f"Path: {p}")
    if all_paths_ok:
        record("PASS", "Project Directory Structure", f"Root: {ROOT_DIR}")

    # 4. Database File (Read-Only Check — Never Mutates)
    db_path = os.path.join(BACKEND_DIR, "app.db")
    if os.path.exists(db_path) and os.path.isfile(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        record("PASS", "Database File: app.db present", f"Size: {size_kb:.1f} KB (Read-only check)")
    else:
        record("WARN", "Database File: app.db not found", "Database will be initialized on first server start.")

    # 5. Port Availability
    b_busy = check_port(BACKEND_PORT)
    f_busy = check_port(FRONTEND_PORT)
    if not b_busy and not f_busy:
        record("PASS", f"Port Availability: Ports {BACKEND_PORT} & {FRONTEND_PORT} free", "No conflict with other local processes.")
    elif b_busy and f_busy:
        record("WARN", f"Port Status: Ports {BACKEND_PORT} & {FRONTEND_PORT} in use", "Existing server instances may already be running.")
    elif b_busy:
        record("WARN", f"Port Status: Backend port {BACKEND_PORT} in use", "Another service is listening on port 8000.")
    else:
        record("WARN", f"Port Status: Frontend port {FRONTEND_PORT} in use", "Another service is listening on port 5173.")

    # 6. Physical LAN IP Discovery
    lan_ip = get_local_ip()
    if lan_ip and not lan_ip.startswith("127."):
        record("PASS", f"Active LAN IPv4: {lan_ip}", f"Mobile access URL: http://{lan_ip}:{FRONTEND_PORT}")
    else:
        record("WARN", "No Physical LAN IPv4 Detected", "Server will only be accessible locally (http://localhost:5173).")

    # 7. Windows Firewall Rules (Platform-Aware)
    if sys.platform == "win32":
        rules = [
            (f"{APP_NAME} - Frontend (Vite)", FRONTEND_PORT),
            (f"{APP_NAME} - Backend (FastAPI)", BACKEND_PORT),
        ]
        fw_ok = True
        for rule_name, port in rules:
            try:
                check = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
                if check.returncode != 0:
                    fw_ok = False
            except Exception:
                fw_ok = False
        if fw_ok:
            record("PASS", "Windows Firewall: Inbound rules configured", "Ports 5173 and 8000 allowed for private LAN.")
        else:
            record("WARN", "Windows Firewall: Inbound rules missing", "Run setup_mobile_access.bat as Admin if remote devices cannot connect.")
    else:
        record("SKIP", "Windows Firewall Check", "Non-Windows platform; firewall check skipped.")

    # Summary
    pass_cnt = results.count("PASS")
    warn_cnt = results.count("WARN")
    fail_cnt = results.count("FAIL")
    skip_cnt = results.count("SKIP")

    sys.stdout.write(f"  {SLATE}{'─' * 60}{RESET}\n")
    sys.stdout.write(f"  {DIM}Doctor Summary:{RESET} {TEAL}{pass_cnt} PASS{RESET}  ")
    if warn_cnt:
        sys.stdout.write(f"{AMBER}{warn_cnt} WARN{RESET}  ")
    if fail_cnt:
        sys.stdout.write(f"{RED}{fail_cnt} FAIL{RESET}  ")
    if skip_cnt:
        sys.stdout.write(f"{GRAY}{skip_cnt} SKIP{RESET}  ")
    sys.stdout.write("\n\n")

    return 1 if fail_cnt > 0 else 0


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


def main(open_browser: bool = False):
    global running
    print_banner()

    # Background firewall check
    threading.Thread(target=ensure_firewall_rules, daemon=True).start()

    start_backend()
    start_frontend()

    # Auto-refresh banner when services come online
    threading.Thread(target=wait_for_services, args=(15.0, open_browser), daemon=True).start()

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


def parse_args():
    parser = argparse.ArgumentParser(
        prog="launcher.py",
        description=f"{APP_NAME} — Control Hub Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
commands:
  doctor           Run read-only pre-flight environment diagnostics (PASS/WARN/FAIL/SKIP)

options:
  -h, --help       Show this help message and exit
  --no-browser     Start services without launching a browser window
"""
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start services without launching a browser window."
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "doctor",
        help="Run read-only pre-flight environment diagnostics (PASS/WARN/FAIL/SKIP)."
    )

    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.command == "doctor":
        sys.exit(run_doctor())
    else:
        main(open_browser=not cli_args.no_browser)

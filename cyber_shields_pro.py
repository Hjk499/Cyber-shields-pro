"""
CYBER SHIELDS PRO V2.2 - MALUKU TECH
Interface modernisée + alertes de ressources et de diagnostic.
Les fonctions d'origine sont conservées. Ajout d'un moteur local expérimental de détection
(EICAR et indicateurs heuristiques simples). Ce moteur ne remplace pas un antivirus complet.
Les ports signalés et les seuils sont des éléments à examiner, pas une preuve d'attaque.
"""
import csv
import platform
import socket
import sqlite3
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import hashlib
import os

try:
    import psutil
except ImportError:
    psutil = None

APP_NAME = "CYBER SHIELDS PRO"
VERSION = "2.2.1"
COMPANY = "MALUKU TECH"
DATA_DIR = Path.home() / "CyberShields"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "cyber_shields.db"
REVIEW_PORTS = {21, 22, 23, 135, 139, 445, 3389, 5900}
BG = "#061426"
PANEL = "#0a1d33"
PANEL2 = "#0d2743"
BLUE = "#087fe5"
CYAN = "#19baff"
TEXT = "#e8f2ff"
MUTED = "#9bb5d2"
GREEN = "#19d994"
ORANGE = "#ffb547"
RED = "#ff5967"


def resource_path(filename):
    """Chemin compatible avec Python et PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / filename


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class CyberShieldsApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {VERSION} | {COMPANY}")
        self.root.geometry("1380x850")
        self.root.minsize(1050, 700)
        self.root.configure(bg=BG)
        # Icône Windows de la fenêtre
        try:
            self.root.iconbitmap(str(resource_path("cyber_shields.ico")))
        except Exception:
            pass
        self.latest = {}
        self.alert_signatures = set()
        self.db_init()
        self.setup_style()
        self.build_ui()
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(15000, self.periodic_refresh)

    def db_init(self):
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, severity TEXT NOT NULL,
                category TEXT NOT NULL, details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'A examiner')""")

    def log_incident(self, severity, category, details):
        with sqlite3.connect(DB_PATH) as con:
            con.execute("INSERT INTO incidents(created_at,severity,category,details) VALUES(?,?,?,?)",
                        (now_text(), severity, category, details))

    def raise_alert(self, severity, category, details, signature):
        # Une seule entrée par condition tant que l'état ne revient pas à la normale.
        if signature not in self.alert_signatures:
            self.alert_signatures.add(signature)
            self.log_incident(severity, category, details)
            self.show_alert(severity, details)

    def clear_alert(self, signature):
        self.alert_signatures.discard(signature)

    def show_alert(self, severity, details):
        if hasattr(self, "alert_banner"):
            color = RED if severity == "Critique" else ORANGE
            self.alert_banner.configure(text=f"  ALERTE {severity.upper()}  •  {details}", fg=color)
        if hasattr(self, "alert_count_var"):
            self.update_alert_count()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=27, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL2, foreground=TEXT,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", BLUE)])
        style.configure("TProgressbar", troughcolor="#18334f", background=CYAN, thickness=12)
        style.configure("TButton", font=("Segoe UI", 10), padding=7)

    def panel(self, parent, title):
        box = tk.Frame(parent, bg=PANEL, highlightbackground="#183b5c", highlightthickness=1)
        tk.Label(box, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=14, pady=(11, 7))
        return box

    def build_ui(self):
        header = tk.Frame(self.root, bg="#04101f", height=88)
        header.pack(fill="x")
        header.pack_propagate(False)
        # Logo officiel Cyber Shields dans l'en-tête
        self.logo_img = None
        try:
            self.logo_img = tk.PhotoImage(file=str(resource_path("cyber_shields_logo.png")))
            # Réduction si le logo est trop grand pour l'en-tête
            factor = max(1, (self.logo_img.width() + 69) // 70)
            if factor > 1:
                self.logo_img = self.logo_img.subsample(factor, factor)
            tk.Label(header, image=self.logo_img, bg="#04101f").pack(side="left", padx=(16, 10))
        except Exception:
            tk.Label(header, text="⬡", bg="#04101f", fg=CYAN, font=("Segoe UI", 38, "bold")).pack(side="left", padx=(20, 8))
        brand = tk.Frame(header, bg="#04101f")
        brand.pack(side="left", pady=13)
        tk.Label(brand, text="Cyber Shields", bg="#04101f", fg=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(brand, text="Protection • Surveillance • Sécurité • PME",
                 bg="#04101f", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(header, text="Votre sécurité, notre priorité", bg="#04101f",
                 fg="#c5dcf5", font=("Segoe UI", 12)).pack(side="right", padx=28)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg="#04182c", width=230)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="ESPACE DE CONTRÔLE", bg="#04182c", fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=17, pady=(20, 12))

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True, padx=18, pady=16)

        self.pages = {}
        for name in ("Tableau de bord", "Surveillance système", "Sécurité réseau", "Maintenance & diagnostic", "Processus", "Incidents & journaux"):
            page = tk.Frame(self.content, bg=BG)
            self.pages[name] = page

        nav = [
            ("⌂", "Tableau de bord"), ("▣", "Surveillance système"),
            ("◎", "Sécurité réseau"), ("⚙", "Maintenance & diagnostic"), ("▤", "Processus"), ("☷", "Incidents & journaux")
        ]
        for icon, name in nav:
            tk.Button(sidebar, text=f"  {icon}   {name}", anchor="w", relief="flat",
                      bd=0, bg="#0757a4" if name == "Tableau de bord" else "#04182c",
                      fg=TEXT, activebackground=BLUE, activeforeground="white",
                      font=("Segoe UI", 10), padx=12, pady=13,
                      command=lambda n=name: self.show_page(n)).pack(fill="x", padx=8, pady=2)
        tk.Frame(sidebar, bg="#183b5c", height=1).pack(fill="x", side="bottom", pady=(0, 1))
        # Identité MALUKU TECH dans la barre latérale
        tk.Label(sidebar, text="CYBER SHIELDS PRO\nMALUKU TECH\nKinshasa - RDC\n\nVersion " + VERSION,
                 bg="#04182c", fg=CYAN, justify="left", font=("Segoe UI", 10, "bold"),
                 padx=18, pady=20).pack(side="bottom", anchor="w")

        self.build_dashboard(self.pages["Tableau de bord"])
        self.build_system(self.pages["Surveillance système"])
        self.build_network(self.pages["Sécurité réseau"])
        self.build_maintenance(self.pages["Maintenance & diagnostic"])
        self.build_processes(self.pages["Processus"])
        self.build_incidents(self.pages["Incidents & journaux"])
        self.show_page("Tableau de bord")

        self.alert_banner = tk.Label(self.root, text="  Surveillance active • seuil d'alerte : 85 %",
                                     bg="#04101f", fg=GREEN, anchor="w", padx=14, pady=7,
                                     font=("Segoe UI", 9))
        self.alert_banner.pack(fill="x", side="bottom")

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    def metric_card(self, parent, label, key):
        card = self.panel(parent, label)
        value = tk.StringVar(value="—")
        tk.Label(card, textvariable=value, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=14, pady=4)
        bar = ttk.Progressbar(card, maximum=100)
        bar.pack(fill="x", padx=14, pady=(4, 14))
        self.metrics[key] = (value, bar)
        return card

    def build_dashboard(self, page):
        tk.Label(page, text="Tableau de bord", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 12))
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        self.metrics = {}
        for label, key in (("PROCESSEUR • CPU", "cpu"), ("MÉMOIRE • RAM", "ram"), ("DISQUE SYSTÈME", "disk")):
            c = self.metric_card(top, label, key)
            c.pack(side="left", fill="both", expand=True, padx=(0, 10))
        mid = tk.Frame(page, bg=BG)
        mid.pack(fill="both", expand=True, pady=12)
        info = self.panel(mid, "INFORMATIONS SYSTÈME")
        info.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.info_var = tk.StringVar(value="Collecte des informations…")
        tk.Label(info, textvariable=self.info_var, bg=PANEL, fg=TEXT, justify="left",
                 font=("Segoe UI", 11), padx=14, pady=12).pack(anchor="w")
        alerts = self.panel(mid, "CENTRE D'ALERTES")
        alerts.pack(side="left", fill="both", expand=True)
        self.alert_count_var = tk.StringVar(value="Chargement des alertes…")
        tk.Label(alerts, textvariable=self.alert_count_var, bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 15, "bold"), padx=14).pack(anchor="w", pady=(10, 5))
        self.alert_list = tk.Text(alerts, height=8, bg="#061426", fg=TEXT,
                                  insertbackground=TEXT, relief="flat", wrap="word",
                                  font=("Segoe UI", 9), state="disabled")
        self.alert_list.pack(fill="both", expand=True, padx=12, pady=6)
        tk.Label(alerts, text="Historique des alertes détectées. Ce module ne constitue pas un antivirus.",
                 bg=PANEL, fg=MUTED, justify="left", padx=14).pack(anchor="w", pady=(0, 8))
        actions = tk.Frame(page, bg=BG)
        actions.pack(fill="x")
        self.button(actions, "Actualiser les mesures", self.refresh_all).pack(side="left", padx=(0, 8))
        self.button(actions, "Exporter rapport CSV", self.export_report).pack(side="left")

    def button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=BLUE, fg="white",
                         activebackground=CYAN, activeforeground="#041426",
                         relief="flat", bd=0, padx=13, pady=8, font=("Segoe UI", 10, "bold"))

    def build_system(self, page):
        tk.Label(page, text="Surveillance système", bg=BG, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(0, 12))
        self.sys_text = tk.StringVar(value="Les mesures apparaîtront ici.")
        box = self.panel(page, "RESSOURCES ET ÉTAT")
        box.pack(fill="both", expand=True)
        tk.Label(box, textvariable=self.sys_text, bg=PANEL, fg=TEXT, justify="left",
                 font=("Segoe UI", 12), padx=16, pady=16).pack(anchor="w")
        self.button(page, "Actualiser", self.refresh_all).pack(anchor="w", pady=10)

    def build_network(self, page):
        tk.Label(page, text="Sécurité réseau", bg=BG, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="Hôte à tester :", bg=BG, fg=TEXT).pack(side="left")
        self.host_entry = tk.Entry(row, width=25, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=("Segoe UI", 11))
        self.host_entry.insert(0, "8.8.8.8")
        self.host_entry.pack(side="left", padx=8, ipady=7)
        self.button(row, "Tester Ping", self.run_ping).pack(side="left", padx=4)
        self.button(row, "Actualiser connexions", self.refresh_connections).pack(side="left", padx=4)
        box = self.panel(page, "RÉSULTATS DU DIAGNOSTIC")
        box.pack(fill="both", expand=True, pady=12)
        self.net_output = tk.Text(box, bg="#061426", fg=TEXT, insertbackground=TEXT,
                                  relief="flat", wrap="word", font=("Consolas", 10))
        self.net_output.pack(fill="both", expand=True, padx=10, pady=10)
        self.net_output.insert("end", "Les connexions affichées dépendent des permissions Windows.\nLes ports signalés demandent une vérification humaine.\n")


    def build_maintenance(self, page):
        tk.Label(page, text="Maintenance & diagnostic", bg=BG, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(page, bg=BG); row.pack(fill="x", pady=(0, 10))
        self.button(row, "Lancer le diagnostic complet", self.run_full_diagnostic).pack(side="left", padx=(0, 8))
        self.button(row, "Analyser les fichiers temporaires", self.scan_temp_files).pack(side="left", padx=(0, 8))
        self.button(row, "Nettoyer fichiers temporaires", self.clean_temp_files).pack(side="left")
        avrow = tk.Frame(page, bg=BG); avrow.pack(fill="x", pady=(0, 10))
        tk.Label(avrow, text="Moteur de détection MALUKU TECH (analyse locale)", bg=BG, fg=CYAN,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))
        self.button(avrow, "Analyse rapide", self.start_quick_scan).pack(side="left", padx=4)
        self.button(avrow, "Choisir un dossier", self.start_custom_scan).pack(side="left", padx=4)
        self.button(avrow, "Analyse du dossier utilisateur", self.start_full_scan).pack(side="left", padx=4)
        box = self.panel(page, "RÉSULTATS ET RECOMMANDATIONS")
        box.pack(fill="both", expand=True)
        self.maintenance_output = tk.Text(box, bg="#061426", fg=TEXT, insertbackground=TEXT,
                                          relief="flat", wrap="word", font=("Consolas", 10))
        self.maintenance_output.pack(fill="both", expand=True, padx=10, pady=10)
        self.maintenance_output.insert("end", "Lancez un diagnostic pour vérifier le système, le stockage et le réseau.\nLe nettoyage ne supprime que les fichiers temporaires accessibles de votre compte Windows.\n")
        self.maintenance_output.insert("end", "\nMOTEUR DE DÉTECTION LOCAL : recherche de la chaîne de test EICAR et de quelques indicateurs heuristiques simples.\nCe moteur expérimental n'est pas un antivirus complet et ne garantit pas la détection des logiciels malveillants.\nAucun fichier n'est supprimé ou mis en quarantaine automatiquement.\n")

    def maintenance_write(self, message):
        self.maintenance_output.insert("end", f"[{now_text()}] {message}\n")
        self.maintenance_output.see("end")

    # --- Moteur local expérimental MALUKU TECH ---
    EICAR_MARKER = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    def start_quick_scan(self):
        roots = [Path.home() / "Downloads", Path.home() / "Desktop"]
        if platform.system() == "Windows":
            roots.extend([Path(os.environ.get("TEMP", str(Path.home() / "AppData/Local/Temp")))])
        roots = [p for p in roots if p.exists() and p.is_dir()]
        self.start_local_scan(roots, "Analyse rapide")

    def start_full_scan(self):
        # Analyse du profil utilisateur uniquement : évite les zones système protégées.
        self.start_local_scan([Path.home()], "Analyse du dossier utilisateur")

    def start_custom_scan(self):
        selected = filedialog.askdirectory(title="Choisir le dossier à analyser")
        if selected:
            self.start_local_scan([Path(selected)], "Analyse personnalisée")

    def start_local_scan(self, roots, label):
        if not roots:
            messagebox.showinfo("Analyse locale", "Aucun dossier accessible à analyser.")
            return
        self.maintenance_write(f"--- {label} démarrée ---")
        self.maintenance_write("Analyse en cours en arrière-plan. Les fichiers ne seront pas modifiés.")
        threading.Thread(target=self._local_scan_worker, args=(roots, label), daemon=True).start()

    def _local_scan_worker(self, roots, label):
        checked = 0
        findings = []
        skipped_dirs = {".git", "node_modules", "venv", ".venv", "Windows", "Program Files", "Program Files (x86)"}
        max_file_size = 50 * 1024 * 1024
        for root in roots:
            for current, dirs, files in os.walk(root, onerror=lambda _e: None):
                dirs[:] = [d for d in dirs if d not in skipped_dirs]
                for name in files:
                    path = Path(current) / name
                    try:
                        if path.is_symlink() or not path.is_file():
                            continue
                        size = path.stat().st_size
                        if size > max_file_size:
                            continue
                        with path.open("rb") as stream:
                            data = stream.read(max_file_size + 1)
                        checked += 1
                        reasons = []
                        if self.EICAR_MARKER in data:
                            reasons.append("signature de test EICAR détectée")
                        lower = name.lower()
                        # Heuristiques indicatives à faible confiance, jamais une preuve de malware.
                        if re.search(r"\.(pdf|doc|jpg|png)\.(exe|scr|bat|cmd|js)$", lower):
                            reasons.append("double extension potentiellement trompeuse")
                        if path.suffix.lower() in {".ps1", ".vbs", ".js", ".bat", ".cmd"} and len(data) > 0:
                            sample = data[:200000].lower()
                            indicators = (b"powershell -enc", b"frombase64string", b"wscript.shell", b"rundll32")
                            if any(token in sample for token in indicators):
                                reasons.append("commande/script à examiner (heuristique)")
                        if reasons:
                            findings.append((str(path), "; ".join(reasons)))
                    except (PermissionError, OSError):
                        continue
        def report():
            self.maintenance_write(f"--- {label} terminée : {checked} fichier(s) examinés ---")
            if findings:
                self.maintenance_write(f"{len(findings)} élément(s) à examiner (ce ne sont pas tous des infections confirmées) :")
                for filename, reason in findings[:100]:
                    self.maintenance_write(f"À VÉRIFIER : {filename} — {reason}")
                    self.log_incident("À examiner", "Analyse locale", f"{filename} — {reason}")
                if len(findings) > 100:
                    self.maintenance_write(f"{len(findings)-100} résultat(s) supplémentaire(s) non affiché(s).")
            else:
                self.maintenance_write("Aucun indicateur ciblé détecté. Cela ne prouve pas que le système est exempt de malware.")
            self.refresh_incidents()
        self.root.after(0, report)

    def run_full_diagnostic(self):
        self.maintenance_write("--- Diagnostic système ---")
        if psutil is None:
            self.maintenance_write("ERREUR : psutil absent. Installez les dépendances.")
            return
        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
            self.maintenance_write(f"CPU : {cpu:.1f}% | RAM : {ram.percent:.1f}% ({ram.available / (1024**3):.1f} Go disponibles)")
            self.maintenance_write(f"Disque {disk_path} : {disk.percent:.1f}% utilisé | {disk.free / (1024**3):.1f} Go libres")
            self.maintenance_write(f"Système : {platform.platform()} | PC : {platform.node()}")
            self.maintenance_write(f"Adresse IP locale : {self.get_local_ip()}")
            try:
                gateway = psutil.net_if_stats()
                active = [name for name, info in gateway.items() if info.isup]
                self.maintenance_write("Interfaces réseau actives : " + (", ".join(active) if active else "aucune détectée"))
            except Exception as exc:
                self.maintenance_write(f"Interfaces réseau : lecture limitée ({exc})")
            if cpu >= 85: self.raise_alert("Élevé" if cpu < 95 else "Critique", "Diagnostic", f"CPU élevé : {cpu:.1f}%", "diag_cpu")
            if ram.percent >= 85: self.raise_alert("Élevé" if ram.percent < 95 else "Critique", "Diagnostic", f"RAM élevée : {ram.percent:.1f}%", "diag_ram")
            if disk.percent >= 85: self.raise_alert("Élevé" if disk.percent < 95 else "Critique", "Diagnostic", f"Disque rempli : {disk.percent:.1f}%", "diag_disk")
            self.maintenance_write("Diagnostic terminé. Les résultats sont des contrôles indicatifs, pas une certification de sécurité.")
            self.refresh_incidents()
        except Exception as exc:
            self.maintenance_write(f"Diagnostic interrompu : {exc}")

    def _temp_files(self):
        import tempfile
        roots = [Path(tempfile.gettempdir())]
        if platform.system() == "Windows":
            roots.append(Path.home() / "AppData" / "Local" / "Temp")
        seen = set()
        for root in roots:
            try:
                resolved = root.resolve()
                if resolved not in seen and resolved.is_dir():
                    seen.add(resolved)
                    yield resolved
            except Exception:
                continue

    def scan_temp_files(self):
        count = total = 0
        for root in self._temp_files():
            for item in root.rglob("*"):
                try:
                    if item.is_file() and not item.is_symlink():
                        count += 1; total += item.stat().st_size
                except (OSError, PermissionError):
                    pass
        self.maintenance_write(f"Analyse terminée : {count} fichier(s) temporaire(s) accessibles, environ {total / (1024**2):.1f} Mo.")
        self.maintenance_write("Certains fichiers peuvent être utilisés par Windows ou des applications et ne sont pas supprimables.")

    def clean_temp_files(self):
        if not messagebox.askyesno("Confirmer le nettoyage", "Supprimer les fichiers temporaires accessibles du compte utilisateur ?\nLes fichiers verrouillés seront ignorés. Cette opération est irréversible."):
            return
        removed = freed = 0
        for root in self._temp_files():
            for item in root.rglob("*"):
                try:
                    if item.is_file() and not item.is_symlink():
                        size = item.stat().st_size
                        item.unlink()
                        removed += 1; freed += size
                except (OSError, PermissionError):
                    pass
        self.maintenance_write(f"Nettoyage terminé : {removed} fichier(s) supprimé(s), environ {freed / (1024**2):.1f} Mo libérés. Les fichiers verrouillés ont été ignorés.")

    def build_processes(self, page):
        tk.Label(page, text="Processus en cours", bg=BG, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(0, 12))
        self.button(page, "Actualiser la liste", self.refresh_processes).pack(anchor="w", pady=(0, 10))
        cols = ("pid", "name", "cpu", "memory")
        self.proc_tree = ttk.Treeview(page, columns=cols, show="headings")
        for col, title, width in [("pid", "PID", 90), ("name", "Nom", 430), ("cpu", "CPU %", 120), ("memory", "RAM %", 120)]:
            self.proc_tree.heading(col, text=title)
            self.proc_tree.column(col, width=width, anchor="w")
        self.proc_tree.pack(fill="both", expand=True)

    def build_incidents(self, page):
        tk.Label(page, text="Incidents & journaux", bg=BG, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", pady=(0, 10))
        self.button(row, "Actualiser", self.refresh_incidents).pack(side="left", padx=(0, 8))
        self.button(row, "Exporter incidents CSV", self.export_incidents).pack(side="left")
        cols = ("date", "severity", "category", "details", "status")
        self.inc_tree = ttk.Treeview(page, columns=cols, show="headings")
        for col, title, width in [("date", "Date", 155), ("severity", "Niveau", 90),
                                  ("category", "Catégorie", 130), ("details", "Détails", 500),
                                  ("status", "Statut", 110)]:
            self.inc_tree.heading(col, text=title)
            self.inc_tree.column(col, width=width, anchor="w")
        self.inc_tree.pack(fill="both", expand=True)

    def periodic_refresh(self):
        self.refresh_all()
        self.root.after(15000, self.periodic_refresh)

    def refresh_all(self):
        if psutil is None:
            self.alert_banner.configure(text="Dépendance absente : installer psutil depuis requirements.txt", fg=RED)
            return
        try:
            cpu = psutil.cpu_percent(interval=0.2)
            ram = psutil.virtual_memory().percent
            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path).percent
            self.latest = {"cpu": cpu, "ram": ram, "disk": disk}
            for key, val in self.latest.items():
                var, bar = self.metrics[key]
                var.set(f"{val:.1f} %")
                bar["value"] = val
                sig = f"resource_{key}"
                if val >= 85:
                    label = {"cpu": "CPU", "ram": "Mémoire RAM", "disk": "Disque"}[key]
                    self.raise_alert("Élevé" if val < 95 else "Critique", "Ressources",
                                     f"{label} utilisé à {val:.1f}% (seuil 85%).", sig)
                else:
                    self.clear_alert(sig)
            self.info_var.set(
                f"Système : {platform.system()} {platform.release()} ({platform.machine()})\n"
                f"Ordinateur : {platform.node()}\nProcesseurs logiques : {psutil.cpu_count()}\n"
                f"Adresse locale : {self.get_local_ip()}\nDernière mesure : {now_text()}"
            )
            self.sys_text.set(
                f"CPU : {cpu:.1f}%\nMémoire RAM : {ram:.1f}%\nDisque système : {disk:.1f}%\n"
                f"Système : {platform.platform()}\nAdresse locale : {self.get_local_ip()}\nMesure : {now_text()}"
            )
            if not any(v >= 85 for v in self.latest.values()):
                self.alert_banner.configure(text="  Surveillance active • Aucun seuil de ressource élevé détecté",
                                            fg=GREEN)
            self.refresh_processes()
            self.refresh_incidents()
            self.update_alert_count()
        except Exception as exc:
            self.alert_banner.configure(text=f"Erreur de lecture système : {exc}", fg=RED)

    def update_alert_count(self):
        with sqlite3.connect(DB_PATH) as con:
            count = con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            recent = con.execute(
                "SELECT created_at, severity, category, details FROM incidents "
                "ORDER BY id DESC LIMIT 8"
            ).fetchall()
        self.alert_count_var.set(f"{count} incident(s) enregistré(s) • 8 derniers maximum")
        if hasattr(self, "alert_list"):
            self.alert_list.configure(state="normal")
            self.alert_list.delete("1.0", "end")
            if not recent:
                self.alert_list.insert("end", "Aucune alerte enregistrée.\nSurveillance active.")
            else:
                for created, severity, category, details in recent:
                    self.alert_list.insert("end", f"[{created}]  {severity.upper()} • {category}\n{details}\n\n")
            self.alert_list.configure(state="disabled")

    def get_local_ip(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except Exception:
            return "Indisponible"
        finally:
            sock.close()

    def run_ping(self):
        host = self.host_entry.get().strip()
        if not host or any(c.isspace() for c in host):
            messagebox.showwarning("Hôte invalide", "Saisissez un nom d'hôte ou une adresse IP valide.")
            return
        self.append_text(f"\n--- Test vers {host} ---\n")
        def worker():
            try:
                flag = "-n" if platform.system() == "Windows" else "-c"
                result = subprocess.run(["ping", flag, "4", host], capture_output=True,
                                         text=True, timeout=15)
                output = result.stdout or result.stderr or "Aucune sortie retournée."
                if result.returncode != 0:
                    self.root.after(0, lambda: self.raise_alert("Moyen", "Réseau",
                        f"Échec du diagnostic Ping vers {host}.", f"ping_{host}"))
                else:
                    self.root.after(0, lambda: self.clear_alert(f"ping_{host}"))
            except Exception as exc:
                output = f"Échec du test : {exc}"
                self.root.after(0, lambda: self.raise_alert("Moyen", "Réseau",
                    f"Impossible d'effectuer le Ping vers {host} : {exc}", f"ping_{host}"))
            self.root.after(0, lambda: self.append_text(output))
        threading.Thread(target=worker, daemon=True).start()

    def append_text(self, text):
        self.net_output.insert("end", text + "\n")
        self.net_output.see("end")

    def refresh_connections(self):
        if psutil is None:
            return
        self.append_text(f"\n--- Connexions observées : {now_text()} ---")
        found = 0
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN:
                    port = conn.laddr.port if conn.laddr else 0
                    line = f"ÉCOUTE | {conn.laddr} | PID {conn.pid or '?'}"
                    if port in REVIEW_PORTS:
                        line += " | À examiner (port de service)"
                        self.raise_alert("À examiner", "Réseau", line, f"port_{port}_{conn.pid}")
                    self.append_text(line)
                    found += 1
            if not found:
                self.append_text("Aucune socket en écoute retournée, ou permissions insuffisantes.")
        except Exception as exc:
            self.append_text(f"Lecture réseau limitée : {exc}")
        self.refresh_incidents()

    def refresh_processes(self):
        if psutil is None or not hasattr(self, "proc_tree"):
            return
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)
        rows = []
        for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
            try:
                rows.append((proc.info["pid"], proc.info.get("name") or "Inconnu",
                             proc.cpu_percent(interval=None), proc.info.get("memory_percent") or 0))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        rows.sort(key=lambda row: row[2], reverse=True)
        for pid, name, cpu, mem in rows[:200]:
            self.proc_tree.insert("", "end", values=(pid, name, f"{cpu:.1f}", f"{mem:.1f}"))

    def refresh_incidents(self):
        if not hasattr(self, "inc_tree"):
            return
        for item in self.inc_tree.get_children():
            self.inc_tree.delete(item)
        with sqlite3.connect(DB_PATH) as con:
            rows = con.execute("SELECT created_at,severity,category,details,status FROM incidents ORDER BY id DESC LIMIT 500").fetchall()
        for row in rows:
            self.inc_tree.insert("", "end", values=row)
        self.update_alert_count()

    def export_report(self):
        if not self.latest:
            messagebox.showinfo("Rapport", "Actualisez d'abord les mesures.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"CyberShields_Rapport_{datetime.now():%Y%m%d_%H%M}.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Produit", APP_NAME]); writer.writerow(["Version", VERSION])
            writer.writerow(["Entreprise", COMPANY]); writer.writerow(["Date", now_text()])
            writer.writerow(["Ordinateur", platform.node()]); writer.writerow(["Système", platform.platform()])
            writer.writerow([]); writer.writerow(["Indicateur", "Valeur (%)"])
            for key, value in self.latest.items():
                writer.writerow([key.upper(), f"{value:.1f}"])
        messagebox.showinfo("Rapport créé", f"Rapport enregistré :\n{path}")

    def export_incidents(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"CyberShields_Incidents_{datetime.now():%Y%m%d_%H%M}.csv")
        if not path:
            return
        with sqlite3.connect(DB_PATH) as con, open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Date", "Niveau", "Catégorie", "Détails", "Statut"])
            writer.writerows(con.execute("SELECT created_at,severity,category,details,status FROM incidents ORDER BY id DESC"))
        messagebox.showinfo("Export terminé", f"Incidents exportés :\n{path}")

    def on_close(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    CyberShieldsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

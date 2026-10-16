#!/usr/bin/env python3
"""
zeitplan.py - Grafische Verwaltung des automatischen Messaufrufs.

Legt per python-crontab einen Crontab-Eintrag des aktuellen Benutzers an,
der main.py im gewaehlten Intervall startet. Die Ausfuehrung uebernimmt
weiterhin cron, die GUI muss dafuer nicht laufen.

Abhaengigkeiten:
    pip install python-crontab croniter
    (Achtung: NICHT das Paket "crontab" installieren, es heisst gleich, ist aber ein anderes.)

Einmalig fuer eine Desktop-Verknuepfung:
    python3 zeitplan.py --verknuepfung
"""

import os
import sys
import shutil
import fcntl
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from crontab import CronTab
except ImportError:
    CronTab = None

APP_TITLE = "Monitoring-Zeitplan"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "messung.log")
LOCK_FILE = "/tmp/tachymeter_monitoring.lock"
JOB_COMMENT = "tachymeter_monitoring"   # Kennung des eigenen Crontab-Eintrags

AUS = "Aus (keine automatische Messung)"
TAEGLICH = "täglich zu fester Uhrzeit"

# Anzeige-Text -> Cron-Ausdruck
INTERVALLE = {
    AUS: None,
    "alle 10 Minuten": "*/10 * * * *",
    "alle 15 Minuten": "*/15 * * * *",
    "alle 20 Minuten": "*/20 * * * *",
    "alle 30 Minuten": "*/30 * * * *",
    "stündlich": "0 * * * *",
    "alle 2 Stunden": "0 */2 * * *",
    "alle 3 Stunden": "0 */3 * * *",
    "alle 4 Stunden": "0 */4 * * *",
    "alle 6 Stunden": "0 */6 * * *",
    "alle 12 Stunden": "0 */12 * * *",
    TAEGLICH: "daily",
}

LOG_ZEILEN = 60


# ==========================================
# HILFSFUNKTIONEN (BACKEND)
# ==========================================
def baue_befehl():
    """Befehl, den cron ausfuehrt. Absolute Pfade, da cron nur ein minimales PATH hat.
    flock -n sorgt dafuer, dass sich Messungen nie ueberlappen (serieller Port!)."""
    flock = shutil.which("flock") or "/usr/bin/flock"
    python = sys.executable
    return (f'cd "{BASE_DIR}" && {flock} -n {LOCK_FILE} '
            f'"{python}" main.py >> "{LOG_FILE}" 2>&1')


def messung_laeuft():
    """Prueft ueber dieselbe Lock-Datei wie flock, ob gerade eine Messung laeuft."""
    try:
        fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o666)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def label_fuer_ausdruck(ausdruck):
    """Ordnet einen vorhandenen Cron-Ausdruck einem Dropdown-Eintrag zu.
    Rueckgabe: (label, stunde, minute) oder (None, None, None) bei benutzerdefiniert."""
    for label, expr in INTERVALLE.items():
        if expr == ausdruck:
            return label, None, None
    teile = ausdruck.split()
    if (len(teile) == 5 and teile[0].isdigit() and teile[1].isdigit()
            and teile[2:] == ["*", "*", "*"]):
        return TAEGLICH, int(teile[1]), int(teile[0])
    return None, None, None


def naechster_lauf(job):
    """Naechster Ausfuehrungszeitpunkt (benoetigt croniter)."""
    try:
        return job.schedule(date_from=datetime.now()).get_next()
    except Exception:
        return None


def lies_log_ende(pfad, n=LOG_ZEILEN):
    if not os.path.exists(pfad):
        return "Noch keine Ausgaben vorhanden."
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as f:
            zeilen = f.readlines()
        return "".join(zeilen[-n:]) or "Log-Datei ist leer."
    except Exception as e:
        return f"Log-Datei nicht lesbar: {e}"


def erstelle_verknuepfung():
    """Legt eine Verknuepfung auf dem Desktop und im Startmenue an."""
    inhalt = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_TITLE}\n"
        "Comment=Automatische Tachymeter-Messung planen\n"
        f'Exec="{sys.executable}" "{os.path.abspath(__file__)}"\n'
        f"Path={BASE_DIR}\n"
        "Icon=appointment-new\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
    ziele = [
        os.path.expanduser("~/.local/share/applications"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Schreibtisch"),
    ]
    erstellt = []
    for ordner in ziele:
        if ordner.endswith(("Desktop", "Schreibtisch")) and not os.path.isdir(ordner):
            continue
        os.makedirs(ordner, exist_ok=True)
        pfad = os.path.join(ordner, "monitoring-zeitplan.desktop")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(inhalt)
        os.chmod(pfad, 0o755)
        erstellt.append(pfad)
    for p in erstellt:
        print(f"Verknüpfung angelegt: {p}")


# ==========================================
# GUI (FRONTEND)
# ==========================================
class ZeitplanApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x600")
        self.root.minsize(620, 480)

        self.cron = None
        self.aktueller_job = None
        self.letzter_log_stand = None

        self.intervall_var = tk.StringVar(value=AUS)
        self.stunde_var = tk.StringVar(value="06")
        self.minute_var = tk.StringVar(value="00")

        self._setup_ui()
        self.lade_status()
        self._auto_refresh()

    # ---------- Aufbau ----------
    def _setup_ui(self):
        haupt = ttk.Frame(self.root, padding=12)
        haupt.pack(fill="both", expand=True)

        # Gruppe 1: Zeitplan
        f_plan = ttk.LabelFrame(haupt, text="  Automatische Messung  ", padding=10)
        f_plan.pack(fill="x")

        ttk.Label(f_plan, text="Intervall:").grid(row=0, column=0, sticky="w")
        self.cb_intervall = ttk.Combobox(f_plan, textvariable=self.intervall_var,
                                         values=list(INTERVALLE), state="readonly", width=34)
        self.cb_intervall.grid(row=0, column=1, sticky="w", padx=8)
        self.cb_intervall.bind("<<ComboboxSelected>>", lambda e: self._zeige_uhrzeit())

        self.f_uhrzeit = ttk.Frame(f_plan)
        ttk.Label(self.f_uhrzeit, text="Uhrzeit:").pack(side="left")
        ttk.Spinbox(self.f_uhrzeit, from_=0, to=23, width=3, format="%02.0f",
                    textvariable=self.stunde_var, wrap=True).pack(side="left", padx=(6, 2))
        ttk.Label(self.f_uhrzeit, text=":").pack(side="left")
        ttk.Spinbox(self.f_uhrzeit, from_=0, to=59, width=3, format="%02.0f",
                    textvariable=self.minute_var, wrap=True).pack(side="left", padx=2)
        ttk.Label(self.f_uhrzeit, text="Uhr").pack(side="left", padx=(4, 0))

        ttk.Button(f_plan, text="Übernehmen", command=self.uebernehmen).grid(
            row=0, column=3, sticky="e", padx=(8, 0))
        f_plan.columnconfigure(2, weight=1)

        ttk.Label(f_plan, foreground="gray",
                  text="Läuft eine Messung zum nächsten Termin noch, wird dieser Termin übersprungen.").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        # Gruppe 2: Status
        f_status = ttk.LabelFrame(haupt, text="  Status  ", padding=10)
        f_status.pack(fill="x", pady=10)

        self.lbl_plan = self._statuszeile(f_status, 0, "Eingestellt:")
        self.lbl_naechste = self._statuszeile(f_status, 1, "Nächste Messung:")
        self.lbl_laeuft = self._statuszeile(f_status, 2, "Messung läuft:")
        self.lbl_warnung = ttk.Label(f_status, text="", foreground="#b35c00", wraplength=680)
        self.lbl_warnung.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        f_btn = ttk.Frame(f_status)
        f_btn.grid(row=0, column=2, rowspan=3, sticky="ne")
        ttk.Button(f_btn, text="Jetzt messen", command=self.jetzt_messen).pack(fill="x")
        ttk.Button(f_btn, text="Aktualisieren", command=self.lade_status).pack(fill="x", pady=(6, 0))
        f_status.columnconfigure(1, weight=1)

        # Gruppe 3: Log
        f_log = ttk.LabelFrame(haupt, text=f"  Letzte Ausgaben ({os.path.relpath(LOG_FILE, BASE_DIR)})  ",
                               padding=6)
        f_log.pack(fill="both", expand=True)
        self.txt_log = tk.Text(f_log, height=12, wrap="none", font=("monospace", 9), state="disabled")
        sb = ttk.Scrollbar(f_log, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _statuszeile(self, parent, row, titel):
        ttk.Label(parent, text=titel).grid(row=row, column=0, sticky="w", pady=2)
        lbl = ttk.Label(parent, text="–", font=("TkDefaultFont", 10, "bold"))
        lbl.grid(row=row, column=1, sticky="w", padx=8)
        return lbl

    def _zeige_uhrzeit(self):
        if self.intervall_var.get() == TAEGLICH:
            self.f_uhrzeit.grid(row=1, column=1, sticky="w", padx=8, pady=(6, 0))
        else:
            self.f_uhrzeit.grid_remove()

    # ---------- Crontab ----------
    def _lade_crontab(self):
        self.cron = CronTab(user=True)
        return self.cron

    def _fremde_jobs(self):
        """Andere Eintraege, die ebenfalls main.py aufrufen (z. B. von Hand angelegt)."""
        return [j for j in self.cron
                if j.comment != JOB_COMMENT and j.is_enabled() and "main.py" in j.command]

    def lade_status(self):
        try:
            self._lade_crontab()
        except Exception as e:
            self.lbl_plan.config(text="Crontab nicht lesbar")
            self.lbl_warnung.config(text=str(e))
            return

        jobs = [j for j in self.cron.find_comment(JOB_COMMENT) if j.is_enabled()]
        self.aktueller_job = jobs[0] if jobs else None

        if self.aktueller_job is None:
            self.intervall_var.set(AUS)
            self.lbl_plan.config(text="keine automatische Messung")
        else:
            ausdruck = str(self.aktueller_job.slices)
            label, h, m = label_fuer_ausdruck(ausdruck)
            if label is None:
                self.lbl_plan.config(text=f"benutzerdefiniert ({ausdruck})")
            else:
                self.intervall_var.set(label)
                if label == TAEGLICH:
                    self.stunde_var.set(f"{h:02d}")
                    self.minute_var.set(f"{m:02d}")
                    self.lbl_plan.config(text=f"täglich um {h:02d}:{m:02d} Uhr")
                else:
                    self.lbl_plan.config(text=label)
        self._zeige_uhrzeit()

        fremde = self._fremde_jobs()
        if fremde:
            self.lbl_warnung.config(
                text="Achtung: Ein weiterer Crontab-Eintrag startet ebenfalls main.py:\n  "
                     + "\n  ".join(str(j) for j in fremde)
                     + "\nBeim Übernehmen wird gefragt, ob er ersetzt werden soll.")
        else:
            self.lbl_warnung.config(text="")

        self._aktualisiere_laufend()

    def uebernehmen(self):
        label = self.intervall_var.get()
        ausdruck = INTERVALLE.get(label)

        if ausdruck == "daily":
            try:
                h, m = int(self.stunde_var.get()), int(self.minute_var.get())
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except ValueError:
                messagebox.showerror(APP_TITLE, "Bitte eine gültige Uhrzeit eingeben.")
                return
            ausdruck = f"{m} {h} * * *"

        try:
            cron = self._lade_crontab()   # frisch einlesen, falls zwischendurch geaendert
            fremde = self._fremde_jobs()
            if fremde:
                antwort = messagebox.askyesnocancel(
                    APP_TITLE,
                    "Es gibt bereits einen anderen Crontab-Eintrag, der main.py startet:\n\n"
                    + "\n".join(str(j) for j in fremde)
                    + "\n\nDiesen Eintrag entfernen und durch den neuen Zeitplan ersetzen?\n"
                      "(Nein = behalten, dann laufen ggf. beide)")
                if antwort is None:
                    return
                if antwort:
                    for j in fremde:
                        cron.remove(j)

            cron.remove_all(comment=JOB_COMMENT)
            if ausdruck:
                os.makedirs(LOG_DIR, exist_ok=True)
                job = cron.new(command=baue_befehl(), comment=JOB_COMMENT)
                job.setall(ausdruck)
                if not job.is_valid():
                    messagebox.showerror(APP_TITLE, f"Ungültiger Zeitplan: {ausdruck}")
                    return
            cron.write()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Crontab konnte nicht geschrieben werden:\n{e}")
            return

        self.lade_status()
        messagebox.showinfo(APP_TITLE, "Zeitplan gespeichert.\n\nEingestellt: "
                            + self.lbl_plan.cget("text"))

    # ---------- Manueller Start ----------
    def jetzt_messen(self):
        if messung_laeuft():
            messagebox.showinfo(APP_TITLE, "Es läuft bereits eine Messung.")
            return
        if not messagebox.askyesno(APP_TITLE, "Das Tachymeter fährt jetzt alle Ziele an.\n"
                                              "Messung starten?"):
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n=== Manueller Start {datetime.now():%d.%m.%Y %H:%M:%S} ===\n")
        # eigene Session, damit die Messung beim Schliessen der GUI weiterlaeuft
        subprocess.Popen(baue_befehl(), shell=True, start_new_session=True)
        self.root.after(1500, self._aktualisiere_laufend)

    # ---------- Laufende Aktualisierung ----------
    def _aktualisiere_laufend(self):
        if messung_laeuft():
            self.lbl_laeuft.config(text="ja", foreground="#1a7f37")
        else:
            self.lbl_laeuft.config(text="nein", foreground="")

        if self.aktueller_job is not None:
            n = naechster_lauf(self.aktueller_job)
            self.lbl_naechste.config(text=n.strftime("%d.%m.%Y %H:%M Uhr") if n
                                     else "(für die Anzeige croniter installieren)")
        else:
            self.lbl_naechste.config(text="–")

        try:
            stand = os.stat(LOG_FILE)
            stand = (stand.st_mtime, stand.st_size)
        except OSError:
            stand = None
        if stand != self.letzter_log_stand:
            self.letzter_log_stand = stand
            self.txt_log.config(state="normal")
            self.txt_log.delete("1.0", "end")
            self.txt_log.insert("1.0", lies_log_ende(LOG_FILE))
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")

    def _auto_refresh(self):
        self._aktualisiere_laufend()
        self.root.after(5000, self._auto_refresh)


def main():
    if "--verknuepfung" in sys.argv:
        erstelle_verknuepfung()
        return

    root = tk.Tk()
    if CronTab is None or not hasattr(CronTab, "find_comment"):
        root.withdraw()
        messagebox.showerror(APP_TITLE, "Das Paket 'python-crontab' fehlt.\n\n"
                                        "Installation:\n  pip install python-crontab croniter\n\n"
                                        "(Nicht das gleichnamige Paket 'crontab' verwenden.)")
        return
    if not os.path.exists(MAIN_SCRIPT):
        root.withdraw()
        messagebox.showerror(APP_TITLE, f"main.py nicht gefunden in:\n{BASE_DIR}")
        return
    ZeitplanApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
"""Riga di comando di MacBook Manager. Senza argomenti apre la GUI."""
import argparse
import json
import os
import subprocess
import sys
import time

from . import HELPER, VERSION, status
from .actions import ACTIONS, BY_ID, available, expand

COLORS = {"ok": "\033[32m●\033[0m", "warn": "\033[33m●\033[0m", "err": "\033[31m●\033[0m", "info": "\033[90m●\033[0m"}
PLAIN = {"ok": "[ok]", "warn": "[!!]", "err": "[XX]", "info": "[  ]"}


def run_action(action_id, out=None):
    """Esegue un'azione; quelle root passano dall'helper via pkexec. Ritorna il codice di uscita."""
    a = BY_ID.get(action_id)
    if not a:
        print("Azione sconosciuta: %s (elenco: macbook-manager actions)" % action_id, file=sys.stderr)
        return 2
    if not available(a):
        print("Azione non disponibile: manca %s" % ", ".join(p for p in a["needs"] if not os.path.exists(p)),
              file=sys.stderr)
        return 2
    if a["root"]:
        return subprocess.run(["pkexec", HELPER, a["id"]], stdout=out, stderr=subprocess.STDOUT if out else None).returncode
    for step in a["steps"]:
        rc = subprocess.run(expand(step), stdout=out, stderr=subprocess.STDOUT if out else None).returncode
        if rc:
            return rc
    return 0


def cmd_status(args):
    items = status.collect()
    if args.json:
        json.dump(items, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    marks = COLORS if sys.stdout.isatty() else PLAIN
    group = None
    for it in items:
        if it["group"] != group:
            group = it["group"]
            print("\n" + group)
        print("  %s %-34s %s" % (marks[it["level"]], it["label"], it["value"]))
        if it["level"] in ("warn", "err") and it["hint"]:
            print("      %s%s" % (it["hint"], "  → macbook-manager run " + it["fix"] if it["fix"] else ""))
    return 1 if any(i["level"] == "err" for i in items) else 0


def cmd_actions(_args):
    group = None
    for a in ACTIONS:
        if a["group"] != group:
            group = a["group"]
            print("\n" + group)
        print("  %-20s %s%s%s" % (a["id"], a["label"], "  (root)" if a["root"] else "",
                                  "" if available(a) else "  [non disponibile]"))
    return 0


def cmd_sleep_report(args):
    hist = status.sleep_history(args.boot)
    if not hist:
        print("Nessuna sospensione in questo avvio.")
        return 0
    print("%-14s %7s %-7s %-9s %-12s %s" % ("inizio", "durata", "modo", "coperchio", "batteria", "risveglio"))
    for c in hist:
        start = time.strftime("%d/%m %H:%M:%S", time.localtime(c["start"]))
        if c["minutes"] is None:
            print(start, "  nessun ritorno registrato")
            continue
        bat = "%d mAh" % c["mah"] if c["mah"] is not None else "-"
        print("%-14s %5.0fm  %-7s %-9s %-12s %s" % (start, c["minutes"], c["mode"], c["lid"], bat, c["cause"]))
    print("\nRisvegli a coperchio chiuso senza aprirlo: %d" % sum(c["spontaneous"] for c in hist))
    return 0


def cmd_touchbar_screenshot(args):
    from . import tbcapture as T
    if not T.renderer_active():
        print("La Touch Bar non è in modalità display con il renderer attivo: niente da catturare.", file=sys.stderr)
        return 1
    cap = T.Capture()
    cap.start()
    try:
        print("Tocca la Touch Bar (o cambia volume/luminosità) entro %d s: fnstrip invia l'immagine solo quando "
              "qualcosa cambia." % args.timeout, flush=True)
        if not cap.wait_frame(args.timeout):
            print("Nessun fotogramma ricevuto.", file=sys.stderr)
            return 1
        path = args.file or T.default_path()
        with open(path, "wb") as f:
            f.write(T.png_bytes(cap.frame))
        print("Salvato: %s (%dx%d)" % (path, T.WIDTH, T.HEIGHT))
        return 0
    finally:
        cap.stop()


def cmd_battery_log(_args):
    from . import battery as B
    s, report = B.log_sample()
    if report:
        print("Report della sessione salvato: " + B.short_text(report))
    return 0


def cmd_battery_report(args):
    from . import battery as B
    reps = B.all_reports(args.days)
    if not reps:
        print("Nessuna sessione a batteria nella cronologia di UPower.")
        return 0
    if args.list:
        print("%-3s %-26s %10s %12s %8s %10s %s" % ("n", "sessione", "durata", "carica", "media", "autonomia", "fattori"))
        for i, r in enumerate(reps):
            print("%-3d %-26s %10s %12s %8s %10s %s" % (
                i, "%s → %s" % (time.strftime("%d/%m %H:%M", time.localtime(r["start"])),
                                time.strftime("%H:%M", time.localtime(r["end"]))),
                B.hm(r["duration_min"]), "%.0f → %.0f %%" % (r["start_pct"], r["end_pct"]),
                "%.1f W" % r["avg_w"] if r["avg_w"] else "-", B.hm(r["projected_h"] * 60) if r["projected_h"] else "-",
                "sì" if r.get("factors") else "no"))
        return 0
    if not 0 <= args.n < len(reps):
        print("Sessione %d inesistente (0-%d, elenco: --list)." % (args.n, len(reps) - 1), file=sys.stderr)
        return 2
    r = reps[args.n]
    if args.json:
        json.dump(r, sys.stdout, ensure_ascii=False, indent=1)
        print()
    elif args.html:
        span = time.time() - r["start"] + 3600
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(B.html_report(r, reps[args.n + 1:args.n + 11], B.upower_history("charge", span),
                                  B.upower_history("rate", span)))
        print("Salvato: %s" % args.html)
    else:
        print("\n".join(B.report_lines(r, reps[args.n + 1:args.n + 11])))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="macbook-manager", description="Stato e azioni rapide del MacBookPro14,3.")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd")
    g = sub.add_parser("gui", help="apre la finestra (predefinito)")
    g.add_argument("--tray", action="store_true", help="parte nascosta nella barra di sistema")
    s = sub.add_parser("status", help="stato di driver, Touch Bar, sospensione, rete, energia")
    s.add_argument("--json", action="store_true")
    sub.add_parser("actions", help="elenca le azioni")
    r = sub.add_parser("run", help="esegue un'azione (quelle root chiedono la password con polkit)")
    r.add_argument("action")
    ts = sub.add_parser("touchbar-screenshot", help="salva l'immagine della Touch Bar (modalità display) in PNG")
    ts.add_argument("file", nargs="?")
    ts.add_argument("--timeout", type=int, default=15)
    sr = sub.add_parser("sleep-report", help="sospensioni dell'avvio attuale (o -1, -2...)")
    sr.add_argument("boot", nargs="?", default="0")
    bl = sub.add_parser("battery-log", help="registra un campione della batteria (lo usa il timer, ogni minuto)")
    bl.set_defaults(_x=None)
    br = sub.add_parser("battery-report", help="report delle sessioni a batteria (0 = la più recente)")
    br.add_argument("n", nargs="?", type=int, default=0)
    br.add_argument("--list", action="store_true", help="elenca le sessioni")
    br.add_argument("--json", action="store_true")
    br.add_argument("--html", metavar="FILE", help="salva il report in HTML, con il grafico")
    br.add_argument("--days", type=int, default=60, help="quanti giorni di cronologia leggere (60)")
    args = p.parse_args(argv)

    if args.cmd in (None, "gui"):
        try:
            from .gui import main as gui_main
        except ImportError as e:
            print("GUI non disponibile (%s): installa pyside6 (sudo pacman -S pyside6)." % e, file=sys.stderr)
            return 1
        return gui_main(tray=getattr(args, "tray", False))
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "actions":
        return cmd_actions(args)
    if args.cmd == "run":
        return run_action(args.action)
    if args.cmd == "touchbar-screenshot":
        return cmd_touchbar_screenshot(args)
    if args.cmd == "sleep-report":
        return cmd_sleep_report(args)
    if args.cmd == "battery-log":
        return cmd_battery_log(args)
    if args.cmd == "battery-report":
        return cmd_battery_report(args)
    return 0

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AdOps · Control Financiero de Publicidad Programática
Aplicación de escritorio en un solo archivo (solo tkinter + ttk, librería estándar).

Pestañas:
  1) Calculadora CPM / eCPM y Margen
  2) Comparador de Fuentes (eCPM y Embudo)
  3) Control de Discrepancias
  4) Historial (se conserva entre sesiones)

Nota de negocio: los clics NO intervienen en el revenue. CPM y eCPM se pagan por
impresión; los clics solo se usan para calcular el CTR.
"""
import csv
import json
import math
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox

# ───────────────────────────── Paleta y tipografía ─────────────────────────────
BG = "#F4F6F9"
CARD = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
MUTED = "#64748B"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
SUCCESS = "#16A34A"
WARN = "#D97706"
DANGER = "#DC2626"
TRACK = "#EEF2F7"
ERR_BG = "#FEF2F2"
TINT = {"ok": "#DCFCE7", "warn": "#FEF3C7", "bad": "#FEE2E2"}

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_KPI = ("Segoe UI", 20, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_SMALL_B = ("Segoe UI", 9, "bold")
FONT_APP = ("Segoe UI", 14, "bold")


# ───────────────────────────── Utilidades numéricas ─────────────────────────────
class FieldError(ValueError):
    """Error de validación asociado a un campo concreto del formulario."""

    def __init__(self, msg, field=None):
        super().__init__(msg)
        self.field = field


def parse_num(text):
    """Convierte texto a float. Acepta punto o coma decimal. Vacío -> None."""
    s = (text or "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"Número inválido: '{text.strip()}'")


def pnum(text, field, label):
    try:
        return parse_num(text)
    except ValueError:
        raise FieldError(f"{label}: '{text.strip()}' no es un número válido.", field)


def to_str(v):
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else str(v)


def money(v, d=2):
    return f"${v:,.{d}f}" if v >= 0 else f"-${abs(v):,.{d}f}"


def pct_s(v, d=2):
    return f"{v:,.{d}f}%"


def num_s(v):
    return "—" if v is None else f"{v:,.0f}"


def safe_pct(a, b):
    if a is None or not b:
        return None
    return a / b * 100


def rate_s(v):
    return "—" if v is None else f"{v:.2f}%"


def money_n(v):
    return "—" if v is None else money(v)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _valid_num(proposed):
    return re.fullmatch(r"[0-9.,]*", proposed) is not None


# ───────────────────────────── Lógica de negocio ─────────────────────────────
def calc_finance(mode, ptype, imps, value, cpm_b, cpm_n, margin_pct):
    """
    mode: 'A' (tengo CPM) | 'B' (tengo Revenue)
    ptype: 'Bruto' | 'Neto' (tipo de precio del valor ingresado)
    Los clics no participan: el revenue por CPM depende solo de las impresiones.
    """
    what = "CPM" if mode == "A" else "Revenue"
    if imps is None or imps <= 0:
        raise FieldError("Las impresiones deben ser mayores a 0.", "imps")
    if value is None or value <= 0:
        raise FieldError(f"Ingresa un {what} mayor a 0.", "value")
    if cpm_b is not None and cpm_b <= 0:
        raise FieldError("El CPM Bruto del intermediario debe ser mayor a 0.", "cb")
    if cpm_n is not None and cpm_n <= 0:
        raise FieldError("El CPM Neto del intermediario debe ser mayor a 0.", "cn")
    if cpm_b and cpm_n and cpm_n > cpm_b:
        raise FieldError("El CPM Neto no puede superar al CPM Bruto.", "cn")
    if margin_pct is not None and not 0 <= margin_pct < 100:
        raise FieldError("El margen debe ser mayor o igual a 0% y menor a 100%.", "mg")

    warns = []
    base = value if mode == "A" else value / imps * 1000  # eCPM del valor ingresado

    if cpm_b and cpm_n:
        m, src = 1 - cpm_n / cpm_b, "CPM Bruto y Neto del intermediario"
        if margin_pct is not None and abs(margin_pct / 100 - m) > 1e-6:
            warns.append("Se ignoró el % de margen: los CPMs del intermediario tienen prioridad.")
    elif margin_pct is not None:
        m, src = margin_pct / 100.0, "% de margen deseado"
    elif ptype == "Bruto" and cpm_n:
        m, src = 1 - cpm_n / base, "CPM Neto del intermediario vs precio ingresado"
        if m < 0:
            raise FieldError("El CPM Neto supera al precio Bruto ingresado.", "cn")
    elif ptype == "Neto" and cpm_b:
        m, src = 1 - base / cpm_b, "CPM Bruto del intermediario vs precio ingresado"
        if m < 0:
            raise FieldError("El CPM Bruto del intermediario es menor al precio Neto ingresado.", "cb")
    else:
        m, src = 0.0, "sin datos de intermediario (0%)"

    if ptype == "Bruto":
        g = base
        n = g * (1 - m)
    else:
        n = base
        g = n / (1 - m)

    if g > 300:
        warns.append(f"El eCPM Bruto resultante ({money(g)}) es inusualmente alto: verifica los datos.")
    if m > 0.6:
        warns.append("Margen superior al 60%: verifica los CPMs del intermediario.")

    rev_g = g * imps / 1000
    rev_n = n * imps / 1000
    profit = rev_g - rev_n
    margin = profit / rev_g * 100 if rev_g else m * 100
    pub = rev_n / rev_g * 100 if rev_g else (1 - m) * 100
    inter = 100 - pub

    imp_s = f"{imps:,.0f}"
    m_s = f"{m * 100:.2f}%"
    if mode == "A":
        f_rev = (f"{imp_s} ÷ 1,000 × {money(g)} (CPM Bruto)" if ptype == "Bruto"
                 else f"{imp_s} ÷ 1,000 × {money(n)} ÷ (1 − {m_s})")
        f_net = (f"{money(rev_g)} × (1 − {m_s})" if ptype == "Bruto"
                 else f"{imp_s} ÷ 1,000 × {money(n)} (CPM Neto)")
    else:
        f_rev = (f"Revenue ingresado (Bruto) = {money(rev_g)}" if ptype == "Bruto"
                 else f"{money(rev_n)} ÷ (1 − {m_s})")
        f_net = (f"{money(rev_g)} × (1 − {m_s})" if ptype == "Bruto"
                 else f"Revenue ingresado (Neto) = {money(rev_n)}")

    return {
        "g": g, "n": n, "rev_g": rev_g, "rev_n": rev_n, "profit": profit,
        "margin": margin, "pub": pub, "inter": inter, "m": m, "src": src, "warns": warns,
        "f": {
            "ecpm_g": f"{money(rev_g)} ÷ {imp_s} × 1,000",
            "ecpm_n": f"{money(rev_n)} ÷ {imp_s} × 1,000",
            "rev_g": f_rev,
            "rev_n": f_net,
            "profit": f"{money(rev_g)} − {money(rev_n)}",
            "margin": f"{money(profit)} ÷ {money(rev_g)} × 100",
        },
    }


def source_metrics(s):
    """Métricas del embudo y financieras de una fuente.

    IMPORTANTE: los clics NO entran en el revenue. Con pago por CPM/eCPM el ingreso
    depende solo de las impresiones; los clics se usan únicamente para el CTR.
    """
    imps = s["imps"]
    req, bids, wins, clicks = s.get("req"), s.get("bids"), s.get("wins"), s.get("clicks")
    fee = s.get("fee", 0) / 100.0
    rev_in = imps / 1000 * s["value"] if s["mode"] == "CPM" else s["value"]
    if s["tipo"] == "Bruto":
        gross = rev_in
        net = gross * (1 - fee)
    else:
        net = rev_in
        gross = net / (1 - fee) if fee < 1 else 0
    return {
        "bid": safe_pct(bids, req),
        "win": safe_pct(wins, bids),
        "render": safe_pct(imps, wins),
        "fill": safe_pct(imps, req),
        "ctr": safe_pct(clicks, imps),
        "gross": gross,
        "net": net,
        "ecpm": net / imps * 1000 if imps else 0,
        "rpm_req": net / req * 1000 if req else None,
        "margin": (gross - net) / gross * 100 if gross else 0,
    }


def totals_of(sources, ms):
    gross = sum(m["gross"] for m in ms)
    net = sum(m["net"] for m in ms)
    imps = sum(s["imps"] for s in sources)
    with_req = [s for s in sources if s.get("req")]
    req = sum(s["req"] for s in with_req)
    imps_r = sum(s["imps"] for s in with_req)
    return {
        "gross": gross, "net": net, "imps": imps,
        "ecpm": net / imps * 1000 if imps else 0,
        "fill": safe_pct(imps_r, req) if req else None,
        "margin": (gross - net) / gross * 100 if gross else 0,
    }


def disc_level(p):
    p = round(abs(p), 6)
    if p <= 5:
        return "ok"
    if p <= 10:
        return "warn"
    return "bad"


DISC_NAME = {"ok": "Normal", "warn": "Tolerable", "bad": "Alerta"}

RANK_METRICS = {
    "eCPM Neto": ("ecpm", money_n),
    "Revenue Neto": ("net", lambda v: "—" if v is None else money(v, 0)),
    "eRPM Req.": ("rpm_req", money_n),
    "Fill Rate": ("fill", rate_s),
    "Win Rate": ("win", rate_s),
    "Render Rate": ("render", rate_s),
    "CTR": ("ctr", rate_s),
}


# ───────────────────────────── Exportación CSV profesional ─────────────────────────────
class N:
    """Número a escribir en el CSV con una cantidad fija de decimales."""
    __slots__ = ("v", "d")

    def __init__(self, v, d=2):
        self.v, self.d = v, d


CSV_PREFS = {"fmt": "latam", "meta": True}
CSV_FORMATS = {"latam": (";", ","), "intl": (",", ".")}


def _cell(v, decimal):
    if v is None:
        return ""
    if isinstance(v, N):
        if v.v is None:
            return ""
        s = f"{v.v:.{v.d}f}"
        return s.replace(".", decimal) if decimal != "." else s
    s = str(v)
    if s and s[0] in "=+-@\t\r":  # evita inyección de fórmulas en Excel
        s = "'" + s
    return s


def write_report(path, delimiter, decimal, include_meta, title, meta, sections, notes=()):
    """Escribe un CSV con aspecto de reporte: cabecera, resumen, tablas con unidades y notas.

    sections: lista de dicts {"kind": "summary"|"data", "title", "headers", "rows"}.
    Con include_meta=False solo se escriben las tablas de datos (listo para BI / pivots).
    Codificación UTF-8 con BOM, para que Excel muestre bien tildes y símbolos.
    """
    data_secs = [s for s in sections if s.get("kind", "data") == "data"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=delimiter, lineterminator="\r\n")

        def row(cells):
            w.writerow([_cell(c, decimal) for c in cells])

        wrote = False
        if include_meta:
            row(["AdOps · Control Financiero"])
            row([title])
            row([])
            for k, v in meta:
                row([k, v])
            wrote = True
        for sec in sections:
            is_data = sec.get("kind", "data") == "data"
            if not include_meta and not is_data:
                continue
            if wrote:
                row([])
            if include_meta or len(data_secs) > 1:
                row([sec["title"]])
            row(sec["headers"])
            for r in sec["rows"]:
                row(r)
            wrote = True
        if include_meta and notes:
            row([])
            row(["NOTAS"])
            for n in notes:
                row([n])
            row([])
            row(["Generado con AdOps · Control Financiero"])


class CsvOptionsDialog(tk.Toplevel):
    """Diálogo modal: formato regional del CSV y si lleva encabezado/resumen."""

    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Exportar a CSV")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.fmt = tk.StringVar(value=CSV_PREFS["fmt"])
        self.meta = tk.BooleanVar(value=CSV_PREFS["meta"])

        body = tk.Frame(self, bg=CARD)
        body.pack(padx=24, pady=20)
        tk.Label(body, text="Exportar a CSV", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x")
        tk.Label(body, text="Elige cómo se va a abrir el archivo:", font=FONT_SMALL,
                 fg=MUTED, bg=CARD, anchor="w").pack(fill="x", pady=(2, 8))
        for value, title, sub in (
                ("latam", "Excel en español (Latinoamérica / España)",
                 "Separador punto y coma · decimales con coma"),
                ("intl", "Formato internacional",
                 "Separador coma · decimales con punto")):
            box = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            box.pack(fill="x", pady=4)
            inner = tk.Frame(box, bg=CARD)
            inner.pack(fill="x", padx=12, pady=8)
            tk.Radiobutton(inner, text=title, variable=self.fmt, value=value, bg=CARD,
                           activebackground=CARD, fg=TEXT, font=FONT_B, selectcolor=CARD,
                           anchor="w", highlightthickness=0, bd=0,
                           cursor="hand2").pack(anchor="w")
            tk.Label(inner, text=sub, font=FONT_SMALL, fg=MUTED, bg=CARD).pack(
                anchor="w", padx=(22, 0))
        tk.Checkbutton(body, text="Incluir encabezado, resumen y notas del reporte",
                       variable=self.meta, bg=CARD, activebackground=CARD, fg=TEXT,
                       font=FONT, selectcolor=CARD, highlightthickness=0, bd=0,
                       cursor="hand2").pack(anchor="w", pady=(10, 0))
        tk.Label(body, text="Desactívalo para obtener solo la tabla de datos "
                            "(ideal para tablas dinámicas o BI).",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", wraplength=380,
                 justify="left").pack(fill="x", padx=(22, 0))

        btns = tk.Frame(body, bg=CARD)
        btns.pack(fill="x", pady=(18, 0))
        FlatButton(btns, "Exportar", self._ok).pack(side="right")
        FlatButton(btns, "Cancelar", self.destroy, style="ghost").pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        p = parent.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.update()
        self._grab()
        self.focus_set()
        self.wait_window()

    def _grab(self, tries=0):
        """Bloquea la ventana principal mientras el diálogo está abierto."""
        try:
            self.grab_set()
        except tk.TclError:
            if tries < 20 and self.winfo_exists():
                self.after(50, lambda: self._grab(tries + 1))

    def _ok(self):
        CSV_PREFS["fmt"] = self.fmt.get()
        CSV_PREFS["meta"] = bool(self.meta.get())
        delim, dec = CSV_FORMATS[self.fmt.get()]
        self.result = (delim, dec, bool(self.meta.get()))
        self.destroy()


def export_flow(parent, slug, title, meta, sections, notes=()):
    """Pregunta formato y ruta, y escribe el reporte CSV. Devuelve la ruta o None."""
    dlg = CsvOptionsDialog(parent)
    if not dlg.result:
        return None
    delim, dec, include_meta = dlg.result
    path = filedialog.asksaveasfilename(
        parent=parent.winfo_toplevel(), defaultextension=".csv",
        initialfile=f"adops_{slug}_{datetime.now():%Y%m%d_%H%M}.csv",
        filetypes=[("CSV", "*.csv"), ("Todos los archivos", "*.*")])
    if not path:
        return None
    try:
        write_report(path, delim, dec, include_meta, title, meta, sections, notes)
    except PermissionError:
        messagebox.showerror("Exportar CSV", "No se pudo escribir el archivo.\n"
                                             "Si está abierto en Excel, ciérralo e inténtalo de nuevo.")
        return None
    except OSError as e:
        messagebox.showerror("Exportar CSV", f"No se pudo guardar el archivo:\n{e}")
        return None
    messagebox.showinfo("Exportación completa", f"Archivo guardado:\n{path}")
    return path


# ───────────────────────────── Historial persistente ─────────────────────────────
class History:
    DIR = os.path.join(os.path.expanduser("~"), ".adops_control_financiero")
    FILE = os.path.join(DIR, "historial.json")
    MAX = 500

    def __init__(self):
        self.items = []
        self.load()

    def load(self):
        try:
            with open(self.FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                self.items = [d for d in data if isinstance(d, dict)
                              and d.get("kind") in ("calc", "disc", "cmp")
                              and isinstance(d.get("data"), dict)]
        except (OSError, ValueError):
            self.items = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.FILE), exist_ok=True)
            tmp = self.FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.items, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.FILE)
        except OSError:
            pass

    def add(self, kind, summary, result, indicator, level, data):
        self.items.append({"ts": now_str(), "kind": kind, "summary": summary,
                           "result": result, "indicator": indicator, "level": level,
                           "data": data})
        del self.items[:-self.MAX]
        self.save()
        return len(self.items)


# ───────────────────────────── Estilos ttk ─────────────────────────────
def setup_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.font", FONT)
    root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    s.configure("TFrame", background=BG)
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
    s.configure("TNotebook.Tab", font=FONT_B, padding=(18, 9), background="#E8EDF3",
                foreground=MUTED, borderwidth=0)
    s.map("TNotebook.Tab",
          background=[("selected", BG), ("active", "#DDE5EE")],
          foreground=[("selected", PRIMARY), ("active", TEXT)])

    s.configure("Modern.TEntry", fieldbackground=CARD, foreground=TEXT, padding=6,
                bordercolor="#CBD5E1", lightcolor="#CBD5E1", darkcolor="#CBD5E1",
                insertcolor=TEXT)
    s.map("Modern.TEntry",
          bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)],
          darkcolor=[("focus", PRIMARY)])

    s.configure("Error.TEntry", fieldbackground=ERR_BG, foreground=TEXT, padding=6,
                bordercolor=DANGER, lightcolor=DANGER, darkcolor=DANGER,
                insertcolor=TEXT)
    s.map("Error.TEntry",
          bordercolor=[("focus", DANGER)], lightcolor=[("focus", DANGER)],
          darkcolor=[("focus", DANGER)])

    s.configure("Modern.TCombobox", fieldbackground=CARD, background=CARD, foreground=TEXT,
                padding=6, arrowcolor=MUTED, bordercolor="#CBD5E1",
                lightcolor="#CBD5E1", darkcolor="#CBD5E1")
    s.map("Modern.TCombobox",
          fieldbackground=[("readonly", CARD)], background=[("readonly", CARD)],
          selectbackground=[("readonly", CARD)], selectforeground=[("readonly", TEXT)],
          bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)],
          darkcolor=[("focus", PRIMARY)])

    s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                rowheight=28, borderwidth=0, font=FONT)
    s.configure("Treeview.Heading", background="#F1F5F9", foreground=TEXT, font=FONT_B,
                relief="flat", padding=(8, 8), borderwidth=0)
    s.map("Treeview.Heading", background=[("active", "#E2E8F0")])

    def fixed_map(option):  # workaround de tags en algunas versiones de Tk 8.6
        return [e for e in s.map("Treeview", query_opt=option)
                if e[:2] != ("!disabled", "!selected")]

    s.map("Treeview",
          foreground=fixed_map("foreground") + [("selected", TEXT)],
          background=fixed_map("background") + [("selected", "#DBEAFE")])

    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background="#CBD5E1", troughcolor=BG,
                    bordercolor=BG, lightcolor="#CBD5E1", darkcolor="#CBD5E1",
                    arrowcolor=MUTED, relief="flat")
        s.map(f"{orient}.TScrollbar", background=[("active", "#94A3B8")])


# ───────────────────────────── Widgets reutilizables ─────────────────────────────
class FlatButton(tk.Button):
    STYLES = {
        "primary": (PRIMARY, "#FFFFFF", PRIMARY_HOVER, PRIMARY),
        "secondary": (CARD, TEXT, "#EEF2F7", "#CBD5E1"),
        "ghost": (CARD, MUTED, "#EEF2F7", BORDER),
        "danger": (CARD, DANGER, "#FEF2F2", "#FECACA"),
    }

    def __init__(self, parent, text, command=None, style="primary", **kw):
        bg, fg, hover, border = self.STYLES[style]
        super().__init__(parent, text=text, command=command, font=FONT_B, bg=bg, fg=fg,
                         activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                         padx=14, pady=7, cursor="hand2", highlightthickness=1,
                         highlightbackground=border, highlightcolor=border, **kw)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class Segmented(tk.Frame):
    """Selector segmentado (toggle) ligado a una StringVar."""

    def __init__(self, parent, options, variable, font=FONT_B, padx=14, pady=7):
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        self.var = variable
        self.buttons = {}
        for i, (value, label) in enumerate(options):
            b = tk.Label(self, text=label, font=font, padx=padx, pady=pady,
                         cursor="hand2", bg=CARD, fg=TEXT)
            b.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 1, 0))
            self.columnconfigure(i, weight=1, uniform="seg")
            b.bind("<Button-1>", lambda e, v=value: self.var.set(v))
            b.bind("<Enter>", lambda e, v=value: self._hover(v, True))
            b.bind("<Leave>", lambda e, v=value: self._hover(v, False))
            self.buttons[value] = b
        self.var.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def _hover(self, value, inside):
        if self.var.get() != value:
            self.buttons[value].config(bg="#EFF4FF" if inside else CARD)

    def refresh(self):
        for value, b in self.buttons.items():
            active = self.var.get() == value
            b.config(bg=PRIMARY if active else CARD, fg="#FFFFFF" if active else TEXT)


class KPICard(tk.Frame):
    def __init__(self, parent, title, accent):
        super().__init__(parent, bg=CARD, highlightbackground=BORDER,
                         highlightcolor=BORDER, highlightthickness=1)
        tk.Frame(self, bg=accent, height=3).pack(fill="x")
        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=16, pady=(10, 12))
        tk.Label(body, text=title, font=FONT_SMALL_B, fg=MUTED, bg=CARD,
                 anchor="w").pack(fill="x")
        self.value = tk.Label(body, text="—", font=FONT_KPI, fg=TEXT, bg=CARD, anchor="w")
        self.value.pack(fill="x", pady=(2, 0))
        self.sub = tk.Label(body, text=" ", font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w")
        self.sub.pack(fill="x")

    def set(self, value, sub=" ", color=TEXT):
        self.value.config(text=value, fg=color)
        self.sub.config(text=sub or " ")


def make_card(parent, padx=16, pady=14):
    outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                     highlightcolor=BORDER, highlightthickness=1)
    inner = tk.Frame(outer, bg=CARD)
    inner.pack(fill="both", expand=True, padx=padx, pady=pady)
    return outer, inner


def field(parent, label, var, numeric=True, width=12):
    f = tk.Frame(parent, bg=CARD)
    lbl = tk.Label(f, text=label, font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w")
    lbl.pack(fill="x")
    kw = {}
    if numeric:
        kw = dict(validate="key", validatecommand=(f.register(_valid_num), "%P"))
    e = ttk.Entry(f, textvariable=var, style="Modern.TEntry", font=FONT, width=width, **kw)
    e.pack(fill="x", pady=(3, 0))
    return f, e, lbl


def combo_field(parent, label, var, values, width=10):
    f = tk.Frame(parent, bg=CARD)
    tk.Label(f, text=label, font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w").pack(fill="x")
    cb = ttk.Combobox(f, textvariable=var, values=values, state="readonly",
                      style="Modern.TCombobox", font=FONT, width=width)
    cb.pack(fill="x", pady=(3, 0))
    return f, cb


def flag_field(entries, key):
    """Marca en rojo el campo con error (key) y deja normales los demás."""
    for k, e in entries.items():
        e.configure(style="Error.TEntry" if k == key else "Modern.TEntry")


def hline(parent, pady=10):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=pady)


# ───────────────────────────── Pestaña 1: Calculadora ─────────────────────────────
class CalcTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.mode = tk.StringVar(value="A")
        self.v = {k: tk.StringVar() for k in ("imps", "value", "cb", "cn", "mg")}
        self.entries = {}
        self.last = None
        self._split = None
        self._build()
        for var in [self.mode, *self.v.values()]:
            var.trace_add("write", self.recalc)
        self.recalc()

    def _build(self):
        kp = tk.Frame(self, bg=BG)
        kp.pack(fill="x")
        for i in range(4):
            kp.columnconfigure(i, weight=1, uniform="kpi")
        self.k_gross = KPICard(kp, "REVENUE BRUTO ($)", PRIMARY)
        self.k_net = KPICard(kp, "PAGO AL PUBLISHER / NETO ($)", WARN)
        self.k_profit = KPICard(kp, "PROFIT ($)", SUCCESS)
        self.k_margin = KPICard(kp, "MARGEN (%)", SUCCESS)
        for i, k in enumerate((self.k_gross, self.k_net, self.k_profit, self.k_margin)):
            k.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.columnconfigure(0, weight=5, uniform="b")
        body.columnconfigure(1, weight=6, uniform="b")
        body.rowconfigure(0, weight=1)

        # ── Entradas
        outer, inner = make_card(body)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(inner, text="Parámetros", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x")
        seg = Segmented(inner, [("A", "A: Tengo CPM → calcular Revenue"),
                                ("B", "B: Tengo Revenue → calcular eCPM")],
                        self.mode, font=FONT_SMALL_B, padx=8, pady=7)
        seg.pack(fill="x", pady=(10, 12))

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1, uniform="r1")
        f1, e1, _ = field(row, "Impresiones", self.v["imps"])
        f1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f2, e2, self.lbl_value = field(row, "CPM Bruto ($)", self.v["value"])
        f2.grid(row=0, column=1, sticky="ew")
        self.entries.update(imps=e1, value=e2)

        hline(inner, pady=12)
        tk.Label(inner, text="Intermediario (opcional)", font=FONT_B, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x")
        tk.Label(inner, text="Ingresa CPM Bruto y Neto, o un % de margen deseado. "
                             "Prioridad: CPMs > margen.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", wraplength=400,
                 justify="left").pack(fill="x", pady=(2, 8))
        row2 = tk.Frame(inner, bg=CARD)
        row2.pack(fill="x")
        row2.columnconfigure((0, 1, 2), weight=1, uniform="r2")
        for i, (key, txt) in enumerate((("cb", "CPM Bruto ($)"), ("cn", "CPM Neto ($)"),
                                        ("mg", "Margen deseado (%)"))):
            fr, e, _ = field(row2, txt, self.v[key], width=8)
            fr.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            self.entries[key] = e

        tk.Label(inner, text="ⓘ Los clics no entran en el revenue: con CPM se cobra por "
                             "impresión. El CTR se analiza en el Comparador.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", wraplength=400,
                 justify="left").pack(fill="x", pady=(12, 0))

        btns = tk.Frame(inner, bg=CARD)
        btns.pack(fill="x", pady=(12, 0))
        FlatButton(btns, "Guardar en historial", self.save).pack(side="left")
        FlatButton(btns, "Exportar CSV", self.export, style="secondary").pack(
            side="left", padx=8)
        btns2 = tk.Frame(inner, bg=CARD)
        btns2.pack(fill="x", pady=(8, 0))
        FlatButton(btns2, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left")
        FlatButton(btns2, "Limpiar", self.clear, style="ghost").pack(side="left", padx=8)
        self.status = tk.Label(inner, text="", font=FONT_SMALL, fg=MUTED, bg=CARD,
                               anchor="w", wraplength=400, justify="left")
        self.status.pack(fill="x", pady=(10, 0))

        # ── Desglose
        outer2, inner2 = make_card(body)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(inner2, text="Desglose y fórmulas aplicadas", font=FONT_TITLE, fg=TEXT,
                 bg=CARD, anchor="w").pack(fill="x", pady=(0, 6))
        grid = tk.Frame(inner2, bg=CARD)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        self.rows = {}
        spec = [("ecpm_g", "eCPM Bruto"), ("ecpm_n", "eCPM Neto"), ("rev_g", "Revenue Bruto"),
                ("rev_n", "Pago al Publisher"), ("profit", "Profit"), ("margin", "Margen")]
        for i, (key, name) in enumerate(spec):
            tk.Label(grid, text=name, font=FONT_B, fg=TEXT, bg=CARD, anchor="w").grid(
                row=2 * i, column=0, sticky="w", pady=5, padx=(0, 12))
            fl = tk.Label(grid, text="", font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w",
                          justify="left", wraplength=290)
            fl.grid(row=2 * i, column=1, sticky="w", padx=(0, 10))
            vl = tk.Label(grid, text="—", font=FONT_B, fg=TEXT, bg=CARD, anchor="e")
            vl.grid(row=2 * i, column=2, sticky="e")
            tk.Frame(grid, bg=BORDER, height=1).grid(row=2 * i + 1, column=0, columnspan=3,
                                                     sticky="ew")
            self.rows[key] = (fl, vl)
        self.meta = tk.Label(inner2, text="", font=FONT_SMALL, fg=MUTED, bg=CARD,
                             anchor="w")
        self.meta.pack(fill="x", pady=(6, 0))

        hline(inner2, pady=8)
        tk.Label(inner2, text="Reparto del Revenue Bruto: Publisher vs Intermediario",
                 font=FONT_B, fg=TEXT, bg=CARD, anchor="w").pack(fill="x")
        self.chart = tk.Canvas(inner2, bg=CARD, height=96, highlightthickness=0)
        self.chart.pack(fill="both", expand=True, pady=(6, 0))
        self.chart.bind("<Configure>", lambda e: self._draw_chart())

    # ── Lógica
    def _update_labels(self):
        t = self.app.price_type.get()
        self.lbl_value.config(
            text=(f"CPM {t} ($)" if self.mode.get() == "A" else f"Revenue {t} ($)"))

    def _reset(self, msg, error=False):
        for k in (self.k_gross, self.k_net, self.k_profit, self.k_margin):
            k.set("—")
        for fl, vl in self.rows.values():
            fl.config(text="")
            vl.config(text="—", fg=TEXT)
        self.meta.config(text="")
        self._split = None
        self.last = None
        self._draw_chart()
        self.status.config(text=msg, fg=DANGER if error else MUTED)

    def recalc(self, *_):
        self._update_labels()
        mode, ptype = self.mode.get(), self.app.price_type.get()
        what = "CPM" if mode == "A" else "Revenue"
        try:
            imps = pnum(self.v["imps"].get(), "imps", "Impresiones")
            value = pnum(self.v["value"].get(), "value", what)
            cb = pnum(self.v["cb"].get(), "cb", "CPM Bruto del intermediario")
            cn = pnum(self.v["cn"].get(), "cn", "CPM Neto del intermediario")
            mg = pnum(self.v["mg"].get(), "mg", "Margen deseado")
            if imps is None or value is None:
                flag_field(self.entries, None)
                self._reset(f"Completa Impresiones y {what} para calcular.")
                return
            r = calc_finance(mode, ptype, imps, value, cb, cn, mg)
        except FieldError as e:
            flag_field(self.entries, e.field)
            self._reset(f"⚠ {e}", error=True)
            return
        flag_field(self.entries, None)

        mcol = SUCCESS if r["margin"] >= 15 else WARN if r["margin"] >= 5 else DANGER
        self.k_gross.set(money(r["rev_g"]), f"eCPM Bruto {money(r['g'])}", PRIMARY)
        self.k_net.set(money(r["rev_n"]), f"eCPM Neto {money(r['n'])}", WARN)
        self.k_profit.set(money(r["profit"]), "Ganancia del intermediario",
                          SUCCESS if r["profit"] >= 0 else DANGER)
        self.k_margin.set(pct_s(r["margin"]), "Profit ÷ Revenue Bruto", mcol)

        vals = {"ecpm_g": money(r["g"]), "ecpm_n": money(r["n"]),
                "rev_g": money(r["rev_g"]), "rev_n": money(r["rev_n"]),
                "profit": money(r["profit"]), "margin": pct_s(r["margin"])}
        for key, (fl, vl) in self.rows.items():
            fl.config(text=r["f"][key])
            vl.config(text=vals[key], fg=TEXT)
        self.rows["profit"][1].config(fg=SUCCESS if r["profit"] >= 0 else DANGER)
        self.rows["margin"][1].config(fg=mcol)
        self.meta.config(text=f"Margen aplicado: {r['m'] * 100:.2f}%  ·  Origen: {r['src']}")
        self._split = (r["pub"], r["inter"])
        self._draw_chart()
        self.last = {"inputs": dict(mode=mode, ptype=ptype, imps=imps, value=value,
                                    cb=cb, cn=cn, mg=mg), "res": r}
        if r["warns"]:
            self.status.config(text="⚠ " + " ".join(r["warns"]), fg=WARN)
        else:
            self.status.config(text="✓ Cálculo actualizado", fg=SUCCESS)

    def _draw_chart(self):
        c = self.chart
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 80:
            return
        if not self._split:
            c.create_text(w / 2, h / 2, text="Sin datos para graficar", font=FONT_SMALL,
                          fill=MUTED)
            return
        left, right, bar_h = 105, 70, 24
        rows = [("Publisher", self._split[0], PRIMARY),
                ("Intermediario", self._split[1], SUCCESS)]
        y = 8
        for label, val, color in rows:
            c.create_text(0, y + bar_h / 2, text=label, anchor="w", font=FONT, fill=TEXT)
            x0, x1 = left, max(left + 10, w - right)
            c.create_rectangle(x0, y, x1, y + bar_h, fill=TRACK, outline="")
            fw = (x1 - x0) * max(0, min(100, val)) / 100
            if fw > 0:
                c.create_rectangle(x0, y, x0 + fw, y + bar_h, fill=color, outline="")
            c.create_text(x1 + 10, y + bar_h / 2, text=f"{val:.1f}%", anchor="w",
                          font=FONT_B, fill=color if val >= 0 else DANGER)
            y += bar_h + 14

    # ── Historial / CSV
    def _need_data(self):
        if not self.last:
            self.status.config(text="⚠ Completa datos válidos antes de guardar o exportar.",
                               fg=WARN)
            return False
        return True

    def save(self):
        if not self._need_data():
            return
        i, r = self.last["inputs"], self.last["res"]
        what = "CPM" if i["mode"] == "A" else "Revenue"
        summary = (f"Modo {i['mode']} · {what} {i['ptype']} {money(i['value'])} · "
                   f"{i['imps']:,.0f} impr.")
        result = (f"Bruto {money(r['rev_g'])} → Publisher {money(r['rev_n'])} · "
                  f"Profit {money(r['profit'])}")
        data = dict(i, rev_g=r["rev_g"], rev_n=r["rev_n"], profit=r["profit"],
                    margin=r["margin"], ecpm_g=r["g"], ecpm_n=r["n"])
        n = self.app.history_add("calc", summary, result, f"Margen {r['margin']:.2f}%",
                                 None, data)
        self.status.config(text=f"✓ Guardado en el historial ({n} registros).", fg=SUCCESS)

    def export(self):
        if not self._need_data():
            return
        i, r = self.last["inputs"], self.last["res"]
        what = "CPM" if i["mode"] == "A" else "Revenue"
        entradas = [["Impresiones", N(i["imps"], 0), "impr."],
                    [f"{what} {i['ptype']}", N(i["value"]), "$"]]
        if i["cb"] is not None:
            entradas.append(["CPM Bruto del intermediario", N(i["cb"]), "$"])
        if i["cn"] is not None:
            entradas.append(["CPM Neto del intermediario", N(i["cn"]), "$"])
        if i["mg"] is not None:
            entradas.append(["Margen deseado", N(i["mg"]), "%"])
        f = r["f"]
        resultados = [
            ["eCPM Bruto", N(r["g"]), "$", f["ecpm_g"]],
            ["eCPM Neto", N(r["n"]), "$", f["ecpm_n"]],
            ["Revenue Bruto", N(r["rev_g"]), "$", f["rev_g"]],
            ["Pago al Publisher / Neto", N(r["rev_n"]), "$", f["rev_n"]],
            ["Profit", N(r["profit"]), "$", f["profit"]],
            ["Margen", N(r["margin"]), "%", f["margin"]],
            ["Publisher (% del Revenue Bruto)", N(r["pub"]), "%",
             "Revenue Neto ÷ Revenue Bruto × 100"],
            ["Intermediario (% del Revenue Bruto)", N(r["inter"]), "%", "100 − % Publisher"],
        ]
        meta = [("Módulo", "Calculadora CPM / eCPM y Margen"), ("Generado", now_str()),
                ("Modo", "A: Tengo CPM → calcular Revenue" if i["mode"] == "A"
                 else "B: Tengo Revenue → calcular eCPM"),
                ("Tipo de precio", "Bruto / Gross" if i["ptype"] == "Bruto" else "Neto / Net"),
                ("Margen aplicado (%)", N(r["m"] * 100)),
                ("Origen del margen", r["src"])]
        sections = [
            {"kind": "summary", "title": "ENTRADAS", "headers": ["Campo", "Valor", "Unidad"],
             "rows": entradas},
            {"kind": "data", "title": "RESULTADOS",
             "headers": ["Concepto", "Valor", "Unidad", "Fórmula aplicada"],
             "rows": resultados},
        ]
        notes = ["Los clics no intervienen en el revenue: el CPM se cobra por impresión.",
                 "Revenue = Impresiones ÷ 1000 × CPM · eCPM = Revenue ÷ Impresiones × 1000."]
        export_flow(self, "calculadora", "Reporte · Calculadora CPM / eCPM y Margen",
                    meta, sections, notes)

    def restore(self, d):
        self.app.price_type.set(d.get("ptype", "Bruto"))
        self.mode.set(d.get("mode", "A"))
        for k in self.v:
            self.v[k].set(to_str(d.get(k)))

    def load_sample(self):
        self.mode.set("A")
        for k, val in (("imps", "1250000"), ("value", "4.50"), ("cb", "4.50"),
                       ("cn", "3.60"), ("mg", "")):
            self.v[k].set(val)

    def clear(self):
        for var in self.v.values():
            var.set("")
        self.mode.set("A")


# ───────────────────────────── Diálogo: comparar 2 fuentes ─────────────────────────────
class CompareDialog(tk.Toplevel):
    METRICS = [("eCPM Neto ($)", "ecpm", money_n, True),
               ("Revenue Neto ($)", "net", money_n, True),
               ("eRPM Neto / 1.000 req. ($)", "rpm_req", money_n, True),
               ("Bid Rate", "bid", rate_s, True),
               ("Win Rate", "win", rate_s, True),
               ("Render Rate", "render", rate_s, True),
               ("Fill Rate", "fill", rate_s, True),
               ("CTR", "ctr", rate_s, True),
               ("Margen del intermediario", "margin", rate_s, None)]

    def __init__(self, parent, sa, ma, sb, mb):
        super().__init__(parent)
        self.title("Comparación de fuentes")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        outer, inner = make_card(self, padx=22, pady=18)
        outer.pack(padx=16, pady=16)

        tk.Label(inner, text="Comparación directa", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x")
        verdict = tk.Label(inner, text="", font=FONT_B, fg=SUCCESS, bg=CARD, anchor="w")
        verdict.pack(fill="x", pady=(2, 10))

        grid = tk.Frame(inner, bg=CARD)
        grid.pack(fill="x")
        heads = ["Métrica", f"A · {sa['name']}", f"B · {sb['name']}", "Diferencia (B − A)",
                 "Mejor"]
        for c, h in enumerate(heads):
            tk.Label(grid, text=h, font=FONT_B, fg=TEXT, bg="#F1F5F9", anchor="w" if c == 0
                     else "e", padx=12, pady=8).grid(row=0, column=c, sticky="nsew")

        wins = {"A": 0, "B": 0}
        total = 0
        for r, (label, key, fmt, higher) in enumerate(self.METRICS, start=1):
            va, vb = ma[key], mb[key]
            bg = CARD if r % 2 else "#F8FAFC"
            if va is None or vb is None:
                diff, best = "—", "—"
            else:
                d = vb - va
                if fmt is rate_s:
                    diff = f"{'+' if d >= 0 else '−'}{abs(d):.2f} pp"
                else:
                    diff = f"{'+' if d >= 0 else '−'}${abs(d):,.2f}"
                if higher is None:
                    best = "—"
                elif abs(d) < 1e-9:
                    best = "Empate"
                else:
                    best = "A" if va > vb else "B"
                    wins[best] += 1
                total += 1 if higher is not None else 0
            cells = [label, fmt(va), fmt(vb), diff,
                     {"A": sa["name"], "B": sb["name"]}.get(best, best)]
            for c, txt in enumerate(cells):
                col = TEXT
                font = FONT
                if c == 4 and best in ("A", "B"):
                    col, font = SUCCESS, FONT_B
                if c in (1, 2) and best in ("A", "B") and ((c == 1) == (best == "A")):
                    col, font = SUCCESS, FONT_B
                tk.Label(grid, text=txt, font=font, fg=col, bg=bg, anchor="w" if c == 0 else "e", padx=12,
                         pady=7).grid(row=r, column=c, sticky="nsew")
        for c in range(5):
            grid.columnconfigure(c, weight=1 if c == 0 else 0)

        if wins["A"] == wins["B"]:
            verdict.config(text=f"Empate técnico: {wins['A']} métricas para cada fuente.",
                           fg=WARN)
        else:
            w = "A" if wins["A"] > wins["B"] else "B"
            name = sa["name"] if w == "A" else sb["name"]
            verdict.config(text=f"★ {name} gana en {wins[w]} de {total} métricas comparables.")
        tk.Label(inner, text="pp = puntos porcentuales. El margen del intermediario no "
                             "se califica como mejor/peor.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w").pack(fill="x", pady=(10, 0))
        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", pady=(12, 0))
        FlatButton(row, "Cerrar", self.destroy, style="secondary").pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        p = parent.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")


# ───────────────────────────── Pestaña 2: Comparador ─────────────────────────────
class CompareTab(ttk.Frame):
    COLS = [("name", "Fuente", 130, "w"), ("pago", "Pago", 112, "center"),
            ("req", "Requests", 96, "e"), ("bids", "Bids", 90, "e"),
            ("wins", "Wins", 86, "e"), ("imps", "Impr.", 90, "e"),
            ("clicks", "Clics", 70, "e"), ("val", "CPM / Rev.", 104, "e"),
            ("bid", "Bid %", 68, "e"), ("win", "Win %", 68, "e"),
            ("render", "Render %", 80, "e"), ("fill", "Fill %", 66, "e"),
            ("ctr", "CTR %", 66, "e"), ("ecpm", "eCPM Neto", 92, "e"),
            ("net", "Rev. Neto", 92, "e"), ("rpm", "eRPM Req.", 88, "e"),
            ("margin", "Margen %", 82, "e")]

    SAMPLE = [
        ("Google AdX", "CPM", "Bruto", 15, 12000000, 5400000, 2100000, 1890000, 9450, 4.80),
        ("Magnite", "eCPM", "Neto", 12, 10000000, 4500000, 1600000, 1420000, 5680, 4970.0),
        ("PubMatic", "CPM", "Bruto", 18, 9800000, 4100000, 1650000, 1485000, 7425, 3.90),
        ("OpenX", "eCPM", "Bruto", 20, 7500000, 2900000, 980000, 862400, 2587, 3880.0),
        ("Index Exchange", "CPM", "Neto", 12, 8800000, 3900000, 1500000, 1410000, 4230, 3.20),
    ]

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.sources = []
        self._ms = []
        self.v = {k: tk.StringVar() for k in
                  ("name", "req", "bids", "wins", "imps", "clicks", "val")}
        self.v["fee"] = tk.StringVar(value="15")
        self.v_mode = tk.StringVar(value="CPM")
        self.v_tipo = tk.StringVar(value=app.price_type.get())
        self.rank_metric = tk.StringVar(value="eCPM Neto")
        self.entries = {}
        self._build()
        self.v_mode.trace_add("write", self._on_mode)
        self.rank_metric.trace_add("write", lambda *a: self._draw_rank())
        self._on_mode()
        self.refresh()

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        top.columnconfigure(0, weight=3, uniform="t")
        top.columnconfigure(1, weight=2, uniform="t")

        # ── Formulario
        outer, inner = make_card(top)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(inner, text="Agregar fuente", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x", pady=(0, 8))
        g = tk.Frame(inner, bg=CARD)
        g.pack(fill="x")
        g.columnconfigure(tuple(range(6)), weight=1, uniform="f")

        fr, e, _ = field(g, "Nombre de la fuente", self.v["name"], numeric=False, width=8)
        fr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 8))
        self.entries["name"] = e
        fr, _ = combo_field(g, "Modo de pago", self.v_mode, ["CPM", "eCPM"], width=6)
        fr.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=(0, 8))
        fr, _ = combo_field(g, "Tipo", self.v_tipo, ["Bruto", "Neto"], width=6)
        fr.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=(0, 8))
        fr, e, _ = field(g, "Fee interm. (%)", self.v["fee"], width=6)
        fr.grid(row=0, column=4, sticky="ew", pady=(0, 8))
        self.entries["fee"] = e

        items = [("req", "Requests"), ("bids", "Bids"), ("wins", "Wins"),
                 ("imps", "Impresiones"), ("clicks", "Clics (opc.)"), ("val", "CPM ($)")]
        for i, (key, txt) in enumerate(items):
            fr, e, lbl = field(g, txt, self.v[key], width=6)
            fr.grid(row=1, column=i, sticky="ew", padx=(0, 0 if i == 5 else 8))
            self.entries[key] = e
            if key == "val":
                self.lbl_val = lbl
        for e in self.entries.values():
            e.bind("<Return>", lambda ev: self.add_source())

        tk.Label(inner, text="ⓘ Los clics NO entran en el revenue: CPM y eCPM se pagan por "
                             "impresión, así que solo se usan para el CTR. El fee es el margen "
                             "del intermediario (convierte Bruto ↔ Neto).",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", justify="left",
                 wraplength=600).pack(fill="x", pady=(10, 0))

        b = tk.Frame(inner, bg=CARD)
        b.pack(fill="x", pady=(12, 0))
        FlatButton(b, "＋ Agregar fuente", self.add_source).pack(side="left")
        FlatButton(b, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left", padx=8)
        FlatButton(b, "Guardar en historial", self.save_snapshot,
                   style="secondary").pack(side="left")
        self.status = tk.Label(inner, font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w",
                               justify="left", wraplength=600, text="")
        self.status.pack(fill="x", pady=(8, 0))

        # ── Ranking
        outer2, inner2 = make_card(top)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        hd = tk.Frame(inner2, bg=CARD)
        hd.pack(fill="x")
        tk.Label(hd, text="Ranking por", font=FONT_TITLE, fg=TEXT, bg=CARD).pack(side="left")
        cb = ttk.Combobox(hd, textvariable=self.rank_metric, values=list(RANK_METRICS),
                          state="readonly", style="Modern.TCombobox", font=FONT, width=13)
        cb.pack(side="left", padx=(8, 0))
        self.rank = tk.Canvas(inner2, bg=CARD, height=190, highlightthickness=0)
        self.rank.pack(fill="both", expand=True, pady=(6, 0))
        self.rank.bind("<Configure>", lambda e: self._draw_rank())

        # ── Tabla
        outer3, inner3 = make_card(self, padx=14, pady=12)
        outer3.pack(fill="both", expand=True, pady=(14, 0))
        head = tk.Frame(inner3, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="Fuentes comparadas", font=FONT_TITLE, fg=TEXT, bg=CARD).pack(
            side="left")
        FlatButton(head, "Exportar CSV", self.export_csv, style="secondary").pack(side="right")
        FlatButton(head, "Vaciar", self.clear_table, style="ghost").pack(side="right", padx=8)
        FlatButton(head, "Eliminar", self.delete_selected, style="danger").pack(side="right")
        FlatButton(head, "Comparar 2 fuentes", self.compare_two,
                   style="secondary").pack(side="right", padx=8)

        info = tk.Frame(inner3, bg=CARD)
        info.pack(fill="x", pady=(6, 8))
        self.banner = tk.Label(info, text="", font=FONT_B, fg=SUCCESS, bg=CARD, anchor="w")
        self.banner.pack(side="left")
        self.totals = tk.Label(info, text="", font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="e")
        self.totals.pack(side="right")

        wrap = tk.Frame(inner3, bg=CARD)
        wrap.pack(fill="both", expand=True)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS], show="headings",
                                 selectmode="extended", height=5)
        for key, title, width, anchor in self.COLS:
            self.tree.heading(key, text=title, anchor="center" if anchor != "w" else "w")
            self.tree.column(key, width=width, minwidth=width, anchor=anchor, stretch=True)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("odd", background=CARD)
        self.tree.tag_configure("even", background="#F8FAFC")
        self.tree.tag_configure("best", background="#DCFCE7", foreground="#166534",
                                font=FONT_B)

    # ── Eventos / lógica
    def _on_mode(self, *_):
        self.lbl_val.config(text="CPM ($)" if self.v_mode.get() == "CPM" else "Revenue ($)")

    def sync_type(self):
        self.v_tipo.set(self.app.price_type.get())

    def _msg(self, text, color=MUTED):
        self.status.config(text=text, fg=color)

    def add_source(self):
        g = lambda k: self.v[k].get()
        what = "CPM" if self.v_mode.get() == "CPM" else "Revenue"
        try:
            imps = pnum(g("imps"), "imps", "Impresiones")
            value = pnum(g("val"), "val", what)
            req = pnum(g("req"), "req", "Requests")
            bids = pnum(g("bids"), "bids", "Bids")
            wins = pnum(g("wins"), "wins", "Wins")
            clicks = pnum(g("clicks"), "clicks", "Clics")
            fee = pnum(g("fee"), "fee", "Fee")
            if imps is None or imps <= 0:
                raise FieldError("Ingresa las impresiones (mayor a 0).", "imps")
            if value is None or value <= 0:
                raise FieldError(f"Ingresa el {what} (mayor a 0).", "val")
            fee = 0.0 if fee is None else fee
            if not 0 <= fee < 100:
                raise FieldError("El fee debe ser mayor o igual a 0% y menor a 100%.", "fee")
            name = g("name").strip()
            if not name:
                k = len(self.sources) + 1
                while any(s["name"].lower() == f"fuente {k}" for s in self.sources):
                    k += 1
                name = f"Fuente {k}"
            if any(s["name"].lower() == name.lower() for s in self.sources):
                raise FieldError(f"Ya existe una fuente llamada '{name}'.", "name")
            prev = None
            for label, key, val in (("Requests", "req", req), ("Bids", "bids", bids),
                                    ("Wins", "wins", wins), ("Impresiones", "imps", imps)):
                if val is None:
                    continue
                if prev and val > prev[2]:
                    raise FieldError(f"Embudo inconsistente: {label} ({val:,.0f}) no puede "
                                     f"superar a {prev[0]} ({prev[2]:,.0f}).", key)
                prev = (label, key, val)
            if clicks is not None and clicks > imps:
                raise FieldError("Los clics no pueden superar a las impresiones.", "clicks")
        except FieldError as e:
            flag_field(self.entries, e.field)
            self._msg(f"⚠ {e}", DANGER)
            return
        flag_field(self.entries, None)
        self.sources.append(dict(name=name, mode=self.v_mode.get(), tipo=self.v_tipo.get(),
                                 fee=fee, req=req, bids=bids, wins=wins, imps=imps,
                                 clicks=clicks, value=value))
        for k in ("name", "req", "bids", "wins", "imps", "clicks", "val"):
            self.v[k].set("")
        self._msg(f"✓ Fuente '{name}' agregada.", SUCCESS)
        self.refresh()

    def load_sample(self):
        self.sources = [dict(name=n, mode=m, tipo=t, fee=f, req=r, bids=b, wins=w,
                             imps=i, clicks=c, value=v)
                        for n, m, t, f, r, b, w, i, c, v in self.SAMPLE]
        flag_field(self.entries, None)
        self._msg("✓ Datos de prueba cargados. Selecciona 2 filas y pulsa «Comparar 2 fuentes».",
                  SUCCESS)
        self.refresh()

    def delete_selected(self):
        idx = sorted((int(i) for i in self.tree.selection()), reverse=True)
        for i in idx:
            del self.sources[i]
        self.refresh()

    def clear_table(self):
        self.sources = []
        self.refresh()

    def clear(self):
        self.sources = []
        for k in ("name", "req", "bids", "wins", "imps", "clicks", "val"):
            self.v[k].set("")
        self.v["fee"].set("15")
        self.v_mode.set("CPM")
        self.sync_type()
        flag_field(self.entries, None)
        self._msg("")
        self.refresh()

    def restore(self, d):
        self.sources = [dict(s) for s in d.get("sources", [])]
        self._msg("✓ Comparación restaurada desde el historial.", SUCCESS)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        ms = [source_metrics(s) for s in self.sources]
        best = max(range(len(ms)), key=lambda i: ms[i]["ecpm"]) if ms else None
        for i, (s, m) in enumerate(zip(self.sources, ms)):
            valtxt = (f"CPM {money(s['value'])}" if s["mode"] == "CPM"
                      else f"Rev {money(s['value'], 0)}")
            name = ("★ " if i == best else "") + s["name"]
            tags = ("best",) if i == best else (("even",) if i % 2 else ("odd",))
            self.tree.insert("", "end", iid=str(i), tags=tags, values=(
                name, f"{s['mode']} · {s['tipo']}", num_s(s.get("req")), num_s(s.get("bids")),
                num_s(s.get("wins")), num_s(s["imps"]), num_s(s.get("clicks")), valtxt,
                rate_s(m["bid"]), rate_s(m["win"]), rate_s(m["render"]), rate_s(m["fill"]),
                rate_s(m["ctr"]), money(m["ecpm"]), money(m["net"], 0), money_n(m["rpm_req"]),
                rate_s(m["margin"])))
        if best is not None:
            self.banner.config(
                text=f"★ Más rentable: {self.sources[best]['name']} · "
                     f"eCPM Neto {money(ms[best]['ecpm'])}", fg=SUCCESS)
            t = totals_of(self.sources, ms)
            self.totals.config(
                text=f"Totales · Revenue Bruto {money(t['gross'], 0)} · Revenue Neto "
                     f"{money(t['net'], 0)} · eCPM Neto ponderado {money(t['ecpm'])} · "
                     f"Fill Rate global {rate_s(t['fill'])}")
        else:
            self.banner.config(text="Agrega fuentes para ver el ranking.", fg=MUTED)
            self.totals.config(text="")
        self._ms = ms
        self._draw_rank()

    def _draw_rank(self):
        c = self.rank
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100:
            return
        ms = self._ms
        if not ms:
            c.create_text(w / 2, h / 2, text="Sin fuentes cargadas", font=FONT_SMALL,
                          fill=MUTED)
            return
        key, fmt = RANK_METRICS[self.rank_metric.get()]
        vals = [m[key] for m in ms]
        order = sorted(range(len(ms)), key=lambda i: (vals[i] is None, -(vals[i] or 0)))
        top = max([v for v in vals if v is not None] or [0]) or 1
        n = len(order)
        row_h = min(34, (h - 4) / n)
        bar_h = max(10, row_h - 10)
        left, right = 128, 70
        for rank, i in enumerate(order):
            y = 2 + rank * row_h
            name = self.sources[i]["name"]
            name = name if len(name) <= 14 else name[:13] + "…"
            col = SUCCESS if rank == 0 and vals[i] is not None else PRIMARY
            c.create_text(0, y + bar_h / 2 + 2, text=f"{rank + 1}. {name}", anchor="w",
                          font=FONT_B if rank == 0 else FONT, fill=TEXT)
            x0, x1 = left, max(left + 10, w - right)
            c.create_rectangle(x0, y, x1, y + bar_h, fill=TRACK, outline="")
            if vals[i] is not None:
                fw = (x1 - x0) * max(0.0, vals[i]) / top
                if fw > 0:
                    c.create_rectangle(x0, y, x0 + fw, y + bar_h, fill=col, outline="")
            c.create_text(x1 + 8, y + bar_h / 2 + 2, text=fmt(vals[i]), anchor="w",
                          font=FONT_B, fill=col)

    def compare_two(self):
        sel = [int(i) for i in self.tree.selection()]
        if len(sel) != 2:
            messagebox.showinfo("Comparar fuentes",
                                "Selecciona exactamente 2 filas de la tabla "
                                "(mantén Ctrl para elegir la segunda).")
            return
        a, b = sel
        CompareDialog(self, self.sources[a], self._ms[a], self.sources[b], self._ms[b])

    def save_snapshot(self):
        if not self.sources:
            self._msg("⚠ Agrega al menos una fuente antes de guardar.", WARN)
            return
        ms = self._ms
        t = totals_of(self.sources, ms)
        best = max(range(len(ms)), key=lambda i: ms[i]["ecpm"])
        data = {"sources": [dict(s) for s in self.sources], "n": len(self.sources),
                "gross": t["gross"], "net": t["net"], "ecpm": t["ecpm"],
                "best": self.sources[best]["name"], "best_ecpm": ms[best]["ecpm"],
                "ptype": self.app.price_type.get()}
        n = self.app.history_add(
            "cmp", f"{len(self.sources)} fuentes comparadas",
            f"Mejor: {data['best']} ({money(data['best_ecpm'])} eCPM Neto)",
            f"eCPM pond. {money(t['ecpm'])}", None, data)
        self._msg(f"✓ Comparación guardada en el historial ({n} registros).", SUCCESS)

    def export_csv(self):
        if not self.sources:
            messagebox.showinfo("Exportar CSV", "No hay fuentes para exportar.")
            return
        ms = self._ms
        t = totals_of(self.sources, ms)
        order = sorted(range(len(ms)), key=lambda i: -ms[i]["ecpm"])
        best, worst = order[0], order[-1]
        detail = []
        for pos, i in enumerate(order, start=1):
            s, m = self.sources[i], ms[i]
            detail.append([
                pos, s["name"], s["mode"], s["tipo"], N(s["fee"]), N(s.get("req"), 0),
                N(s.get("bids"), 0), N(s.get("wins"), 0), N(s["imps"], 0),
                N(s.get("clicks"), 0), N(s["value"]), N(m["bid"]), N(m["win"]),
                N(m["render"]), N(m["fill"]), N(m["ctr"]), N(m["gross"]), N(m["net"]),
                N(m["ecpm"]), N(m["rpm_req"]), N(m["margin"]), "Sí" if i == best else ""])
        headers = ["Ranking", "Fuente", "Modo de pago", "Tipo de precio", "Fee interm. (%)",
                   "Requests", "Bids", "Wins", "Impresiones", "Clics",
                   "CPM / Revenue ingresado ($)", "Bid Rate (%)", "Win Rate (%)",
                   "Render Rate (%)", "Fill Rate (%)", "CTR (%)", "Revenue Bruto ($)",
                   "Revenue Neto ($)", "eCPM Neto ($)", "eRPM Neto / 1000 req. ($)",
                   "Margen (%)", "Más rentable"]
        resumen = [
            ["Fuentes comparadas", N(len(self.sources), 0)],
            ["Revenue Bruto total ($)", N(t["gross"])],
            ["Revenue Neto total ($)", N(t["net"])],
            ["eCPM Neto ponderado ($)", N(t["ecpm"])],
            ["Fill Rate global (%)", N(t["fill"])],
            ["Margen global del intermediario (%)", N(t["margin"])],
            ["Fuente más rentable (eCPM Neto)", self.sources[best]["name"]],
            ["eCPM Neto de la mejor fuente ($)", N(ms[best]["ecpm"])],
        ]
        if len(order) > 1 and ms[worst]["ecpm"] > 0:
            gap = (ms[best]["ecpm"] - ms[worst]["ecpm"]) / ms[worst]["ecpm"] * 100
            resumen.append(["Brecha mejor vs. peor fuente (%)", N(gap)])
        meta = [("Módulo", "Comparador de Fuentes (eCPM y Embudo)"),
                ("Generado", now_str()),
                ("Tipo de precio global", "Bruto / Gross" if self.app.price_type.get() == "Bruto"
                 else "Neto / Net"),
                ("Fuentes", str(len(self.sources)))]
        sections = [
            {"kind": "summary", "title": "RESUMEN", "headers": ["Métrica", "Valor"],
             "rows": resumen},
            {"kind": "data", "title": "DETALLE POR FUENTE (ordenado por eCPM Neto)",
             "headers": headers, "rows": detail},
        ]
        notes = [
            "eCPM Neto = Revenue Neto ÷ Impresiones × 1000.",
            "eRPM Neto / 1000 req. = Revenue Neto ÷ Requests × 1000.",
            "Bid Rate = Bids ÷ Requests · Win Rate = Wins ÷ Bids · "
            "Render Rate = Impresiones ÷ Wins · Fill Rate = Impresiones ÷ Requests.",
            "Los clics no intervienen en el revenue (CPM / eCPM se pagan por impresión): "
            "solo se usan para el CTR = Clics ÷ Impresiones.",
            "Las celdas vacías indican datos no informados.",
        ]
        export_flow(self, "comparador_fuentes", "Reporte · Comparador de Fuentes",
                    meta, sections, notes)


# ───────────────────────────── Pestaña 3: Discrepancias ─────────────────────────────
class DiscTab(ttk.Frame):
    LEVELS = {
        "ok": ("NORMAL", SUCCESS,
               "Discrepancia dentro del rango normal (≤ 5%). No se requiere acción."),
        "warn": ("TOLERABLE", WARN,
                 "Discrepancia tolerable (5% – 10%). Monitorea la tendencia y compara por "
                 "día, placement y formato."),
        "bad": ("ALERTA", DANGER,
                "Discrepancia alta (> 10%). Revisa el render (ads servidos pero no "
                "mostrados), la medición (ventana de conteo, viewability, zona horaria) "
                "y el IVT / tráfico inválido."),
    }
    DIM = {"bad": "#5B1F1F", "warn": "#5B4413", "ok": "#14452A"}
    ON = {"bad": DANGER, "warn": WARN, "ok": SUCCESS}
    SAMPLES = [
        ("2000000", "1840000", "8000", "7520"),    # amarillo
        ("1000000", "982000", "4200", "4130"),     # verde
        ("1500000", "1290000", "6000", "5100"),    # rojo
    ]

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.v = {k: tk.StringVar() for k in ("own", "par", "ro", "rp")}
        self.entries = {}
        self.last = None
        self._sample_i = 0
        self._build()
        for var in self.v.values():
            var.trace_add("write", self.recalc)
        self.recalc()

    def _build(self):
        kp = tk.Frame(self, bg=BG)
        kp.pack(fill="x")
        for i in range(4):
            kp.columnconfigure(i, weight=1, uniform="kpi")
        self.k_abs = KPICard(kp, "DIFERENCIA ABSOLUTA (IMPRESIONES)", PRIMARY)
        self.k_pct = KPICard(kp, "DISCREPANCIA (%) IMPRESIONES", PRIMARY)
        self.k_rabs = KPICard(kp, "DIFERENCIA REVENUE ($)", PRIMARY)
        self.k_rpct = KPICard(kp, "DISCREPANCIA (%) REVENUE", PRIMARY)
        for i, k in enumerate((self.k_abs, self.k_pct, self.k_rabs, self.k_rpct)):
            k.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.columnconfigure(0, weight=5, uniform="b")
        body.columnconfigure(1, weight=6, uniform="b")
        body.rowconfigure(0, weight=1)

        outer, inner = make_card(body)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(inner, text="Comparar mis datos vs Partner", font=FONT_TITLE, fg=TEXT,
                 bg=CARD, anchor="w").pack(fill="x", pady=(0, 10))
        g = tk.Frame(inner, bg=CARD)
        g.pack(fill="x")
        g.columnconfigure((0, 1), weight=1, uniform="d")
        spec = [("own", "Impresiones propias", 0, 0), ("par", "Impresiones Partner", 0, 1),
                ("ro", "Revenue propio ($, opcional)", 1, 0),
                ("rp", "Revenue Partner ($, opcional)", 1, 1)]
        for key, txt, r, c in spec:
            fr, e, _ = field(g, txt, self.v[key])
            fr.grid(row=r, column=c, sticky="ew", padx=(0, 8) if c == 0 else 0,
                    pady=(0, 10))
            self.entries[key] = e
        tk.Label(inner, text="Discrepancia % = (Partner − Propias) ÷ Propias × 100.\n"
                             "El semáforo usa el mayor valor absoluto entre impresiones y revenue.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", justify="left").pack(
            fill="x", pady=(0, 10))
        b = tk.Frame(inner, bg=CARD)
        b.pack(fill="x", pady=(4, 0))
        FlatButton(b, "Guardar en historial", self.save).pack(side="left")
        FlatButton(b, "Exportar CSV", self.export, style="secondary").pack(
            side="left", padx=8)
        b2 = tk.Frame(inner, bg=CARD)
        b2.pack(fill="x", pady=(8, 0))
        FlatButton(b2, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left")
        FlatButton(b2, "Limpiar", self.clear, style="ghost").pack(side="left", padx=8)
        self.status = tk.Label(inner, text="", font=FONT_SMALL, fg=MUTED, bg=CARD,
                               anchor="w", wraplength=420, justify="left")
        self.status.pack(fill="x", pady=(10, 0))

        outer2, inner2 = make_card(body)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(inner2, text="Semáforo de discrepancia", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x", pady=(0, 8))
        sem = tk.Frame(inner2, bg=CARD)
        sem.pack(fill="both", expand=True)
        self.light = tk.Canvas(sem, width=92, height=212, bg=CARD, highlightthickness=0)
        self.light.pack(side="left", padx=(0, 18))
        txt = tk.Frame(sem, bg=CARD)
        txt.pack(side="left", fill="both", expand=True)
        self.l_title = tk.Label(txt, text="SIN DATOS", font=FONT_KPI, fg=MUTED, bg=CARD,
                                anchor="w")
        self.l_title.pack(fill="x")
        self.l_pct = tk.Label(txt, text="", font=FONT_B, fg=TEXT, bg=CARD, anchor="w",
                              justify="left", wraplength=330)
        self.l_pct.pack(fill="x", pady=(2, 6))
        self.l_desc = tk.Label(txt, text="Ingresa impresiones propias y del partner.",
                               font=FONT, fg=MUTED, bg=CARD, anchor="w", justify="left",
                               wraplength=330)
        self.l_desc.pack(fill="x")
        hline(txt, pady=12)
        for color, label in ((SUCCESS, "Verde  ≤ 5%  ·  normal"),
                             (WARN, "Amarillo  5% – 10%  ·  tolerable"),
                             (DANGER, "Rojo  > 10%  ·  alerta: revisar render, medición o IVT")):
            row = tk.Frame(txt, bg=CARD)
            row.pack(fill="x", pady=2)
            dot = tk.Canvas(row, width=14, height=14, bg=CARD, highlightthickness=0)
            dot.create_oval(2, 2, 12, 12, fill=color, outline="")
            dot.pack(side="left", padx=(0, 8))
            tk.Label(row, text=label, font=FONT_SMALL, fg=MUTED, bg=CARD,
                     anchor="w", wraplength=320, justify="left").pack(side="left")
        self._draw_light(None)

    def _draw_light(self, level):
        c = self.light
        c.delete("all")
        c.create_rectangle(6, 4, 86, 208, fill="#1E293B", outline="#0F172A", width=2)
        for i, lv in enumerate(("bad", "warn", "ok")):
            cy = 38 + i * 68
            active = level == lv
            if active:
                c.create_oval(46 - 34, cy - 34, 46 + 34, cy + 34, fill="", outline=self.ON[lv],
                              width=2)
            c.create_oval(46 - 26, cy - 26, 46 + 26, cy + 26,
                          fill=self.ON[lv] if active else self.DIM[lv], outline="")

    def _reset(self, msg, error=False):
        for k in (self.k_abs, self.k_pct, self.k_rabs, self.k_rpct):
            k.set("—")
        self.l_title.config(text="SIN DATOS", fg=MUTED)
        self.l_pct.config(text="")
        self.l_desc.config(text="Ingresa impresiones propias y del partner.", fg=MUTED)
        self._draw_light(None)
        self.last = None
        self.status.config(text=msg, fg=DANGER if error else MUTED)

    def recalc(self, *_):
        try:
            own = pnum(self.v["own"].get(), "own", "Impresiones propias")
            par = pnum(self.v["par"].get(), "par", "Impresiones Partner")
            ro = pnum(self.v["ro"].get(), "ro", "Revenue propio")
            rp = pnum(self.v["rp"].get(), "rp", "Revenue Partner")
            if own is not None and own <= 0:
                raise FieldError("Las impresiones propias deben ser mayores a 0.", "own")
            if ro is not None and ro <= 0:
                raise FieldError("El revenue propio debe ser mayor a 0.", "ro")
        except FieldError as e:
            flag_field(self.entries, e.field)
            self._reset(f"⚠ {e}", error=True)
            return
        flag_field(self.entries, None)
        if own is None or par is None:
            self._reset("Completa Impresiones propias y Partner para calcular.")
            return

        diff = par - own
        pct = diff / own * 100
        col_i = self.ON[disc_level(pct)]
        self.k_abs.set(f"{diff:+,.0f}", f"Propias {own:,.0f} vs Partner {par:,.0f}", col_i)
        self.k_pct.set(f"{pct:+.2f}%", "(Partner − Propias) ÷ Propias", col_i)

        worst, worst_src = abs(pct), "impresiones"
        rdiff = rpct = None
        have_rev = ro is not None and rp is not None
        if have_rev:
            rdiff = rp - ro
            rpct = rdiff / ro * 100
            col_r = self.ON[disc_level(rpct)]
            self.k_rabs.set(f"{'+' if rdiff >= 0 else '-'}${abs(rdiff):,.2f}",
                            f"Propio {money(ro)} vs Partner {money(rp)}", col_r)
            self.k_rpct.set(f"{rpct:+.2f}%", "(Partner − Propio) ÷ Propio", col_r)
            if abs(rpct) > worst:
                worst, worst_src = abs(rpct), "revenue"
        else:
            self.k_rabs.set("—", "Revenue opcional", MUTED)
            self.k_rpct.set("—", "Revenue opcional", MUTED)

        lv = disc_level(worst)
        title, color, desc = self.LEVELS[lv]
        self.l_title.config(text=title, fg=color)
        direction = "menos" if pct < 0 else "más"
        self.l_pct.config(
            text=f"Discrepancia máxima: {worst:.2f}% ({worst_src}) · Partner reporta "
                 f"{abs(pct):.2f}% {direction} impresiones")
        self.l_desc.config(text=desc, fg=TEXT)
        self._draw_light(lv)
        self.last = dict(own=own, par=par, ro=ro if have_rev else None,
                         rp=rp if have_rev else None, diff=diff, pct=pct, rdiff=rdiff,
                         rpct=rpct, level=lv, worst=worst, worst_src=worst_src)
        if (ro is None) != (rp is None):
            self.status.config(text="⚠ Completa ambos revenues (propio y partner) para "
                                    "compararlos.", fg=WARN)
        else:
            self.status.config(text="✓ Cálculo actualizado", fg=SUCCESS)

    def save(self):
        d = self.last
        if not d:
            self.status.config(text="⚠ Completa datos válidos antes de guardar.", fg=WARN)
            return
        summary = f"Propias {d['own']:,.0f} vs Partner {d['par']:,.0f} impr."
        result = f"Dif. {d['diff']:+,.0f} impr. ({d['pct']:+.2f}%)"
        if d["rpct"] is not None:
            result += f" · Revenue {d['rpct']:+.2f}%"
        n = self.app.history_add(
            "disc", summary, result,
            f"{DISC_NAME[d['level']]} · máx {d['worst']:.2f}%", d["level"], dict(d))
        self.status.config(text=f"✓ Guardado en el historial ({n} registros).", fg=SUCCESS)

    def export(self):
        d = self.last
        if not d:
            self.status.config(text="⚠ Completa datos válidos antes de exportar.", fg=WARN)
            return
        est_i = DISC_NAME[disc_level(d["pct"])]
        rows = [["Impresiones", N(d["own"], 0), N(d["par"], 0), N(d["diff"], 0),
                 N(d["pct"]), est_i]]
        if d["rpct"] is not None:
            rows.append(["Revenue ($)", N(d["ro"]), N(d["rp"]), N(d["rdiff"]), N(d["rpct"]),
                         DISC_NAME[disc_level(d["rpct"])]])
        meta = [("Módulo", "Control de Discrepancias"), ("Generado", now_str()),
                ("Estado global", DISC_NAME[d["level"]]),
                ("Discrepancia máxima (%)", N(d["worst"])),
                ("Origen de la discrepancia máxima", d["worst_src"])]
        sections = [
            {"kind": "summary", "title": "CRITERIO DEL SEMÁFORO",
             "headers": ["Estado", "Rango de discrepancia", "Acción sugerida"],
             "rows": [["Normal", "≤ 5%", "Sin acción"],
                      ["Tolerable", "5% – 10%", "Monitorear por día, placement y formato"],
                      ["Alerta", "> 10%", "Revisar render, medición e IVT"]]},
            {"kind": "data", "title": "COMPARACIÓN PROPIO VS PARTNER",
             "headers": ["Métrica", "Propio", "Partner", "Diferencia (Partner − Propio)",
                         "Discrepancia (%)", "Estado"], "rows": rows},
        ]
        notes = ["Discrepancia (%) = (Partner − Propio) ÷ Propio × 100.",
                 "Un valor negativo indica que el partner reporta menos que los datos propios.",
                 "El estado global usa el mayor valor absoluto entre impresiones y revenue."]
        export_flow(self, "discrepancias", "Reporte · Control de Discrepancias",
                    meta, sections, notes)

    def restore(self, d):
        for k in self.v:
            self.v[k].set(to_str(d.get(k)))

    def load_sample(self):
        own, par, ro, rp = self.SAMPLES[self._sample_i % len(self.SAMPLES)]
        self._sample_i += 1
        for k, val in zip(("own", "par", "ro", "rp"), (own, par, ro, rp)):
            self.v[k].set(val)

    def clear(self):
        for var in self.v.values():
            var.set("")


# ───────────────────────────── Pestaña 4: Historial ─────────────────────────────
class HistoryTab(ttk.Frame):
    KINDS = {"calc": "Calculadora", "disc": "Discrepancias", "cmp": "Comparador"}

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.filter = tk.StringVar(value="Todos")
        outer, inner = make_card(self, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="Historial de cálculos", font=FONT_TITLE, fg=TEXT,
                 bg=CARD).pack(side="left")
        self.count = tk.Label(head, text="", font=FONT_SMALL, fg=MUTED, bg=CARD)
        self.count.pack(side="left", padx=12)
        cb = ttk.Combobox(head, textvariable=self.filter, state="readonly", width=14,
                          values=["Todos", *self.KINDS.values()], style="Modern.TCombobox",
                          font=FONT)
        cb.pack(side="right")
        tk.Label(head, text="Mostrar:", font=FONT_SMALL, fg=MUTED, bg=CARD).pack(
            side="right", padx=(0, 8))
        self.filter.trace_add("write", lambda *a: self.refresh())

        tk.Label(inner, text="Guarda cálculos desde cualquier pestaña con «Guardar en "
                             "historial». Se conservan al cerrar la app. Doble clic en una "
                             "fila para restaurarla.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", justify="left",
                 wraplength=900).pack(fill="x", pady=(4, 10))

        wrap = tk.Frame(inner, bg=CARD)
        wrap.pack(fill="both", expand=True)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        cols = [("n", "#", 46, "center"), ("ts", "Fecha y hora", 160, "w"),
                ("kind", "Módulo", 120, "w"), ("summary", "Entradas", 340, "w"),
                ("result", "Resultado", 380, "w"), ("ind", "Indicador", 220, "w")]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                                 selectmode="extended")
        for key, title, width, anchor in cols:
            self.tree.heading(key, text=title, anchor="w" if anchor == "w" else "center")
            self.tree.column(key, width=width, minwidth=width, anchor=anchor,
                             stretch=key in ("summary", "result"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("odd", background=CARD)
        self.tree.tag_configure("even", background="#F8FAFC")
        for lv, color in TINT.items():
            self.tree.tag_configure(lv, background=color)
        self.tree.bind("<Double-1>", lambda e: self.restore())
        self.empty = tk.Label(wrap, text="Todavía no hay registros.\nGuarda un cálculo desde "
                                         "cualquier pestaña y aparecerá aquí.",
                              font=FONT, fg=MUTED, bg=CARD, justify="center")

        btns = tk.Frame(inner, bg=CARD)
        btns.pack(fill="x", pady=(12, 0))
        FlatButton(btns, "Restaurar selección", self.restore).pack(side="left")
        FlatButton(btns, "Eliminar", self.delete_selected, style="danger").pack(
            side="left", padx=8)
        FlatButton(btns, "Vaciar historial", self.clear_all, style="ghost").pack(side="left")
        FlatButton(btns, "Exportar CSV", self.export, style="secondary").pack(side="right")
        self.refresh()

    def _visible(self):
        f = self.filter.get()
        inv = {v: k for k, v in self.KINDS.items()}
        items = self.app.history.items
        return [i for i in range(len(items) - 1, -1, -1)
                if f == "Todos" or items[i]["kind"] == inv.get(f)]

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        items = self.app.history.items
        shown = self._visible()
        for pos, idx in enumerate(shown):
            it = items[idx]
            lv = it.get("level")
            tag = lv if lv in TINT else ("even" if pos % 2 else "odd")
            self.tree.insert("", "end", iid=str(idx), tags=(tag,), values=(
                idx + 1, it.get("ts", ""), self.KINDS.get(it["kind"], it["kind"]),
                it.get("summary", ""), it.get("result", ""), it.get("indicator", "")))
        self.count.config(text=f"{len(shown)} de {len(items)} registros")
        if shown:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")

    def restore(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Historial", "Selecciona un registro para restaurarlo.")
            return
        self.app.restore(self.app.history.items[int(sel[0])])

    def delete_selected(self):
        sel = sorted((int(i) for i in self.tree.selection()), reverse=True)
        if not sel:
            return
        for i in sel:
            del self.app.history.items[i]
        self.app.history.save()
        self.refresh()

    def clear_all(self):
        if not self.app.history.items:
            return
        if messagebox.askyesno("Vaciar historial",
                               "¿Eliminar todos los registros del historial?\n"
                               "Esta acción no se puede deshacer."):
            self.app.history.items.clear()
            self.app.history.save()
            self.refresh()

    def export(self):
        items = self.app.history.items
        shown = self._visible()
        if not shown:
            messagebox.showinfo("Exportar CSV", "No hay registros para exportar.")
            return
        calc, disc, cmpr = [], [], []
        for idx in shown:  # más recientes primero
            it, d = items[idx], items[idx]["data"]
            ts = it.get("ts", "")
            if it["kind"] == "calc":
                calc.append([ts, "A · CPM → Revenue" if d.get("mode") == "A"
                             else "B · Revenue → eCPM", d.get("ptype", ""),
                             N(d.get("imps"), 0), N(d.get("value")), N(d.get("cb")),
                             N(d.get("cn")), N(d.get("mg")), N(d.get("ecpm_g")),
                             N(d.get("ecpm_n")), N(d.get("rev_g")), N(d.get("rev_n")),
                             N(d.get("profit")), N(d.get("margin"))])
            elif it["kind"] == "disc":
                disc.append([ts, N(d.get("own"), 0), N(d.get("par"), 0), N(d.get("diff"), 0),
                             N(d.get("pct")), N(d.get("ro")), N(d.get("rp")),
                             N(d.get("rdiff")), N(d.get("rpct")),
                             DISC_NAME.get(d.get("level"), "")])
            else:
                cmpr.append([ts, d.get("ptype", ""), N(d.get("n"), 0), N(d.get("gross")),
                             N(d.get("net")), N(d.get("ecpm")), d.get("best", ""),
                             N(d.get("best_ecpm"))])
        sections = []
        if calc:
            sections.append({"kind": "data", "title": "CALCULADORA CPM / eCPM Y MARGEN",
                             "headers": ["Fecha y hora", "Modo", "Tipo de precio",
                                         "Impresiones", "Valor ingresado: CPM o Revenue ($)",
                                         "CPM Bruto interm. ($)", "CPM Neto interm. ($)",
                                         "Margen deseado (%)", "eCPM Bruto ($)",
                                         "eCPM Neto ($)", "Revenue Bruto ($)",
                                         "Pago al Publisher ($)", "Profit ($)", "Margen (%)"],
                             "rows": calc})
        if disc:
            sections.append({"kind": "data", "title": "CONTROL DE DISCREPANCIAS",
                             "headers": ["Fecha y hora", "Impresiones propias",
                                         "Impresiones partner", "Diferencia (impr.)",
                                         "Discrepancia impr. (%)", "Revenue propio ($)",
                                         "Revenue partner ($)", "Diferencia revenue ($)",
                                         "Discrepancia revenue (%)", "Estado"],
                             "rows": disc})
        if cmpr:
            sections.append({"kind": "data", "title": "COMPARADOR DE FUENTES",
                             "headers": ["Fecha y hora", "Tipo de precio global", "Fuentes",
                                         "Revenue Bruto total ($)", "Revenue Neto total ($)",
                                         "eCPM Neto ponderado ($)", "Fuente más rentable",
                                         "eCPM Neto mejor fuente ($)"], "rows": cmpr})
        meta = [("Módulo", "Historial de cálculos"), ("Generado", now_str()),
                ("Registros exportados", str(len(shown))),
                ("Filtro", self.filter.get())]
        notes = ["Registros ordenados del más reciente al más antiguo.",
                 "Los clics no intervienen en el revenue; solo se usan para el CTR."]
        export_flow(self, "historial", "Reporte · Historial de cálculos", meta, sections,
                    notes)


# ───────────────────────────── Aplicación principal ─────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AdOps · Control Financiero de Publicidad Programática")
        self.geometry("1180x780")
        self.minsize(1050, 680)
        self._set_icon()
        setup_style(self)
        self.price_type = tk.StringVar(value="Bruto")
        self.history = History()
        self._build_header()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(10, 14))
        self.tab_calc = CalcTab(self.nb, self)
        self.tab_cmp = CompareTab(self.nb, self)
        self.tab_disc = DiscTab(self.nb, self)
        self.tab_hist = HistoryTab(self.nb, self)
        self.nb.add(self.tab_calc, text="  Calculadora CPM / eCPM y Margen  ")
        self.nb.add(self.tab_cmp, text="  Comparador de Fuentes (eCPM y Embudo)  ")
        self.nb.add(self.tab_disc, text="  Control de Discrepancias  ")
        self.nb.add(self.tab_hist, text="  Historial  ")

        self.price_type.trace_add("write", self._on_price_type)

    def _set_icon(self):
        """Icono de la ventana dibujado por código (no requiere archivos externos)."""
        try:
            size, r = 64, 14
            img = tk.PhotoImage(width=size, height=size)
            for y in range(size):
                d = min(y, size - 1 - y)
                inset = 0 if d >= r else r - int(math.sqrt(r * r - (r - d) ** 2))
                img.put(PRIMARY, to=(inset, y, size - inset, y + 1))
            base = 50
            for x0, h, color in ((13, 14, "#BFDBFE"), (26, 24, "#FFFFFF"), (39, 34, "#86EFAC")):
                img.put(color, to=(x0, base - h, x0 + 12, base))
            img.put("#FFFFFF", to=(10, base, 54, base + 3))
            self._icon_img = img  # mantener referencia para que no se libere
            self.iconphoto(True, img)
        except Exception:
            pass

    def _build_header(self):
        bar = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightcolor=BORDER,
                       highlightthickness=1)
        bar.pack(fill="x")
        inner = tk.Frame(bar, bg=CARD)
        inner.pack(fill="x", padx=20, pady=12)

        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left")
        tk.Label(left, text="AdOps · Control Financiero", font=FONT_APP, fg=TEXT,
                 bg=CARD, anchor="w").pack(fill="x")
        tk.Label(left, text="Publicidad programática: CPM, eCPM, embudo y discrepancias",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w").pack(fill="x")

        self.btn_menu = FlatButton(inner, "Limpiar / Cargar ejemplo  ▾", self._popup_menu,
                                   style="secondary")
        self.btn_menu.pack(side="right")
        Segmented(inner, [("Bruto", "Bruto / Gross"), ("Neto", "Neto / Net")],
                  self.price_type).pack(side="right", padx=(0, 14))
        tk.Label(inner, text="Tipo de precio:", font=FONT_B, fg=MUTED, bg=CARD).pack(
            side="right", padx=(0, 8))

        self.menu = tk.Menu(self, tearoff=0, font=FONT, bg=CARD, fg=TEXT,
                            activebackground=PRIMARY, activeforeground="#FFFFFF", bd=0)
        self.menu.add_command(label="Cargar ejemplo (todas las pestañas)",
                              command=self.load_all)
        self.menu.add_command(label="Limpiar formularios (no borra el historial)",
                              command=self.clear_all)

    def _popup_menu(self):
        b = self.btn_menu
        try:
            self.menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            self.menu.grab_release()

    def _on_price_type(self, *_):
        self.tab_calc.recalc()
        self.tab_cmp.sync_type()

    def history_add(self, kind, summary, result, indicator, level, data):
        n = self.history.add(kind, summary, result, indicator, level, data)
        self.tab_hist.refresh()
        return n

    def restore(self, item):
        kind, data = item.get("kind"), item.get("data", {})
        if kind == "calc":
            self.tab_calc.restore(data)
            self.nb.select(self.tab_calc)
        elif kind == "disc":
            self.tab_disc.restore(data)
            self.nb.select(self.tab_disc)
        elif kind == "cmp":
            self.tab_cmp.restore(data)
            self.nb.select(self.tab_cmp)

    def load_all(self):
        self.tab_calc.load_sample()
        self.tab_cmp.load_sample()
        self.tab_disc.load_sample()

    def clear_all(self):
        self.tab_calc.clear()
        self.tab_cmp.clear()
        self.tab_disc.clear()


def main():
    try:  # nitidez en Windows con pantallas HiDPI
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AdOps · Control Financiero de Publicidad Programática
Aplicación de escritorio en un solo archivo (solo tkinter + ttk, librería estándar).

Pestañas:
  1) Calculadora CPM / eCPM y Margen
  2) Comparador de Fuentes (eCPM y Embudo)
  3) Control de Discrepancias
"""
import csv
import re
import tkinter as tk
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

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_KPI = ("Segoe UI", 20, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_SMALL_B = ("Segoe UI", 9, "bold")
FONT_APP = ("Segoe UI", 14, "bold")


# ───────────────────────────── Utilidades numéricas ─────────────────────────────
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


def money(v, d=2):
    return f"${v:,.{d}f}" if v >= 0 else f"-${abs(v):,.{d}f}"


def pct_s(v, d=2):
    return f"{v:,.{d}f}%"


def num_s(v):
    return f"{v:,.0f}"


def safe_pct(a, b):
    return None if not b else a / b * 100


def rate_s(v):
    return "—" if v is None else f"{v:.2f}%"


def _valid_num(proposed):
    return re.fullmatch(r"[0-9.,]*", proposed) is not None


# ───────────────────────────── Lógica de negocio ─────────────────────────────
def calc_finance(mode, ptype, imps, value, cpm_b, cpm_n, margin_pct):
    """
    mode: 'A' (tengo CPM) | 'B' (tengo Revenue)
    ptype: 'Bruto' | 'Neto' (tipo de precio del valor ingresado)
    """
    if imps is None or imps <= 0:
        raise ValueError("Las impresiones deben ser mayores a 0.")
    if value is None or value < 0:
        raise ValueError("Ingresa un valor válido (CPM o Revenue).")

    base = value if mode == "A" else value / imps * 1000  # eCPM del valor ingresado

    if cpm_b and cpm_n:
        m, src = 1 - cpm_n / cpm_b, "CPM Bruto y Neto del intermediario"
    elif margin_pct is not None:
        m, src = margin_pct / 100.0, "% de margen deseado"
    elif ptype == "Bruto" and cpm_n and base > 0:
        m, src = 1 - cpm_n / base, "CPM Neto del intermediario vs precio ingresado"
    elif ptype == "Neto" and cpm_b and cpm_b > 0:
        m, src = 1 - base / cpm_b, "CPM Bruto del intermediario vs precio ingresado"
    else:
        m, src = 0.0, "sin datos de intermediario (0%)"
    if m >= 1:
        raise ValueError("El margen debe ser menor al 100%.")

    if ptype == "Bruto":
        g = base
        n = g * (1 - m)
    else:
        n = base
        g = n / (1 - m)

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
        "margin": margin, "pub": pub, "inter": inter, "m": m, "src": src,
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
    """Métricas del embudo y financieras de una fuente."""
    imps, req, bids, wins = s["imps"], s["req"], s["bids"], s["wins"]
    fee = s["fee"] / 100.0
    if s["mode"] == "CPM":
        rev_in = imps / 1000 * s["value"]
    else:
        rev_in = s["value"]
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
        "gross": gross,
        "net": net,
        "ecpm": net / imps * 1000 if imps else 0,
        "margin": (gross - net) / gross * 100 if gross else 0,
    }


def disc_level(p):
    p = round(abs(p), 6)
    if p <= 5:
        return "ok"
    if p <= 10:
        return "warn"
    return "bad"


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

    s.configure("Vertical.TScrollbar", background="#CBD5E1", troughcolor=BG,
                bordercolor=BG, lightcolor="#CBD5E1", darkcolor="#CBD5E1",
                arrowcolor=MUTED, relief="flat")
    s.map("Vertical.TScrollbar", background=[("active", "#94A3B8")])


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


def hline(parent, pady=10):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=pady)


# ───────────────────────────── Pestaña 1: Calculadora ─────────────────────────────
class CalcTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.mode = tk.StringVar(value="A")
        self.v_imps = tk.StringVar()
        self.v_value = tk.StringVar()
        self.v_cb = tk.StringVar()
        self.v_cn = tk.StringVar()
        self.v_mg = tk.StringVar()
        self._split = None
        self._build()
        for v in (self.mode, self.v_imps, self.v_value, self.v_cb, self.v_cn, self.v_mg):
            v.trace_add("write", self.recalc)
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
        f1, _, _ = field(row, "Impresiones", self.v_imps)
        f1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        f2, _, self.lbl_value = field(row, "CPM Bruto ($)", self.v_value)
        f2.grid(row=0, column=1, sticky="ew")

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
        for i, (txt, var) in enumerate((("CPM Bruto ($)", self.v_cb),
                                        ("CPM Neto ($)", self.v_cn),
                                        ("Margen deseado (%)", self.v_mg))):
            fr, _, _ = field(row2, txt, var, width=8)
            fr.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))

        btns = tk.Frame(inner, bg=CARD)
        btns.pack(fill="x", pady=(16, 0))
        FlatButton(btns, "Calcular", self.recalc).pack(side="left")
        FlatButton(btns, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left", padx=8)
        FlatButton(btns, "Limpiar", self.clear, style="ghost").pack(side="left")
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
        self._draw_chart()
        self.status.config(text=msg, fg=DANGER if error else MUTED)

    def recalc(self, *_):
        self._update_labels()
        mode, ptype = self.mode.get(), self.app.price_type.get()
        try:
            imps = parse_num(self.v_imps.get())
            value = parse_num(self.v_value.get())
            if imps is None or value is None:
                what = "CPM" if mode == "A" else "Revenue"
                self._reset(f"Completa Impresiones y {what} para calcular.")
                return
            r = calc_finance(mode, ptype, imps, value, parse_num(self.v_cb.get()),
                             parse_num(self.v_cn.get()), parse_num(self.v_mg.get()))
        except ValueError as e:
            self._reset(f"⚠ {e}", error=True)
            return

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

    def load_sample(self):
        self.mode.set("A")
        self.v_imps.set("1250000")
        self.v_value.set("4.50")
        self.v_cb.set("4.50")
        self.v_cn.set("3.60")
        self.v_mg.set("")

    def clear(self):
        for v in (self.v_imps, self.v_value, self.v_cb, self.v_cn, self.v_mg):
            v.set("")
        self.mode.set("A")


# ───────────────────────────── Pestaña 2: Comparador ─────────────────────────────
class CompareTab(ttk.Frame):
    COLS = [("name", "Fuente", 120, "w"), ("mode", "Modo", 55, "center"),
            ("type", "Tipo", 55, "center"), ("req", "Requests", 80, "e"),
            ("bids", "Bids", 75, "e"), ("wins", "Wins", 70, "e"),
            ("imps", "Impr.", 75, "e"), ("val", "CPM / Rev.", 90, "e"),
            ("bid", "Bid %", 58, "e"), ("win", "Win %", 58, "e"),
            ("render", "Render %", 68, "e"), ("fill", "Fill %", 58, "e"),
            ("ecpm", "eCPM Neto", 82, "e"), ("margin", "Margen %", 72, "e")]

    SAMPLE = [
        ("Google AdX", "CPM", "Bruto", 15, 12000000, 5400000, 2100000, 1890000, 4.80),
        ("Magnite", "eCPM", "Neto", 12, 10000000, 4500000, 1600000, 1420000, 4970.0),
        ("PubMatic", "CPM", "Bruto", 18, 9800000, 4100000, 1650000, 1485000, 3.90),
        ("OpenX", "eCPM", "Bruto", 20, 7500000, 2900000, 980000, 862400, 3880.0),
        ("Index Exchange", "CPM", "Neto", 12, 8800000, 3900000, 1500000, 1410000, 3.20),
    ]

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.sources = []
        self.v_name = tk.StringVar()
        self.v_mode = tk.StringVar(value="CPM")
        self.v_tipo = tk.StringVar(value=app.price_type.get())
        self.v_fee = tk.StringVar(value="15")
        self.v_req = tk.StringVar()
        self.v_bids = tk.StringVar()
        self.v_wins = tk.StringVar()
        self.v_imps = tk.StringVar()
        self.v_val = tk.StringVar()
        self._build()
        self.v_mode.trace_add("write", self._on_mode)
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
        g.columnconfigure(tuple(range(5)), weight=1, uniform="f")
        self.entries = []
        fr, e, _ = field(g, "Nombre de la fuente", self.v_name, numeric=False)
        fr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 8))
        self.entries.append(e)
        fr, _ = combo_field(g, "Modo de pago", self.v_mode, ["CPM", "eCPM"])
        fr.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=(0, 8))
        fr, _ = combo_field(g, "Tipo", self.v_tipo, ["Bruto", "Neto"])
        fr.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=(0, 8))
        fr, e, _ = field(g, "Fee interm. (%)", self.v_fee)
        fr.grid(row=0, column=4, sticky="ew", pady=(0, 8))
        self.entries.append(e)
        items = [("Requests", self.v_req), ("Bids", self.v_bids), ("Wins", self.v_wins),
                 ("Impresiones", self.v_imps), ("CPM ($)", self.v_val)]
        for i, (txt, var) in enumerate(items):
            fr, e, lbl = field(g, txt, var)
            fr.grid(row=1, column=i, sticky="ew", padx=(0, 0 if i == 4 else 8))
            self.entries.append(e)
            if var is self.v_val:
                self.lbl_val = lbl
        for e in self.entries:
            e.bind("<Return>", lambda ev: self.add_source())

        b = tk.Frame(inner, bg=CARD)
        b.pack(fill="x", pady=(14, 0))
        FlatButton(b, "＋ Agregar fuente", self.add_source).pack(side="left")
        FlatButton(b, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left", padx=8)
        self.status = tk.Label(inner, font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w",
                               justify="left", wraplength=520,
                               text="Fee = margen del intermediario; se usa para convertir "
                                    "Bruto ↔ Neto.")
        self.status.pack(fill="x", pady=(10, 0))

        # ── Ranking
        outer2, inner2 = make_card(top)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(inner2, text="Ranking por eCPM Neto", font=FONT_TITLE, fg=TEXT, bg=CARD,
                 anchor="w").pack(fill="x")
        self.rank = tk.Canvas(inner2, bg=CARD, height=190, highlightthickness=0)
        self.rank.pack(fill="both", expand=True, pady=(6, 0))
        self.rank.bind("<Configure>", lambda e: self._draw_rank())

        # ── Tabla
        outer3, inner3 = make_card(self, padx=14, pady=12)
        outer3.pack(fill="both", expand=True, pady=(14, 0))
        head = tk.Frame(inner3, bg=CARD)
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text="Fuentes comparadas", font=FONT_TITLE, fg=TEXT, bg=CARD).pack(
            side="left")
        self.banner = tk.Label(head, text="", font=FONT_B, fg=SUCCESS, bg=CARD)
        self.banner.pack(side="left", padx=14)
        FlatButton(head, "Exportar CSV", self.export_csv, style="secondary").pack(side="right")
        FlatButton(head, "Vaciar tabla", self.clear_table, style="ghost").pack(
            side="right", padx=8)
        FlatButton(head, "Eliminar seleccionada", self.delete_selected,
                   style="danger").pack(side="right")

        wrap = tk.Frame(inner3, bg=CARD)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS], show="headings",
                                 selectmode="extended", height=6)
        for key, title, width, anchor in self.COLS:
            self.tree.heading(key, text=title, anchor="center" if anchor != "w" else "w")
            self.tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
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
        try:
            imps = parse_num(self.v_imps.get())
            value = parse_num(self.v_val.get())
            req = parse_num(self.v_req.get()) or 0
            bids = parse_num(self.v_bids.get()) or 0
            wins = parse_num(self.v_wins.get()) or 0
            fee = parse_num(self.v_fee.get()) or 0
        except ValueError as e:
            self._msg(f"⚠ {e}", DANGER)
            return
        if not imps or imps <= 0:
            self._msg("⚠ Ingresa las impresiones (mayor a 0).", DANGER)
            return
        if value is None:
            self._msg("⚠ Ingresa el CPM o el Revenue.", DANGER)
            return
        if fee >= 100:
            self._msg("⚠ El fee debe ser menor al 100%.", DANGER)
            return
        seq = [(n, v) for n, v in (("Requests", req), ("Bids", bids), ("Wins", wins),
                                   ("Impresiones", imps)) if v > 0]
        for (na, va), (nb, vb) in zip(seq, seq[1:]):
            if vb > va:
                self._msg(f"⚠ Embudo inconsistente: {nb} no puede superar a {na}.", DANGER)
                return
        name = self.v_name.get().strip() or f"Fuente {len(self.sources) + 1}"
        self.sources.append(dict(name=name, mode=self.v_mode.get(), tipo=self.v_tipo.get(),
                                 fee=fee, req=req, bids=bids, wins=wins, imps=imps,
                                 value=value))
        for v in (self.v_name, self.v_req, self.v_bids, self.v_wins, self.v_imps, self.v_val):
            v.set("")
        self._msg(f"✓ Fuente '{name}' agregada.", SUCCESS)
        self.refresh()

    def load_sample(self):
        self.sources = [dict(name=n, mode=m, tipo=t, fee=f, req=r, bids=b, wins=w,
                             imps=i, value=v)
                        for n, m, t, f, r, b, w, i, v in self.SAMPLE]
        self._msg("✓ Datos de prueba cargados.", SUCCESS)
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
        for v in (self.v_name, self.v_req, self.v_bids, self.v_wins, self.v_imps, self.v_val):
            v.set("")
        self.v_mode.set("CPM")
        self.v_fee.set("15")
        self.sync_type()
        self._msg("Fee = margen del intermediario; se usa para convertir Bruto ↔ Neto.")
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        ms = [source_metrics(s) for s in self.sources]
        best = max(range(len(ms)), key=lambda i: ms[i]["ecpm"]) if ms else None
        for i, (s, m) in enumerate(zip(self.sources, ms)):
            valtxt = f"CPM {money(s['value'])}" if s["mode"] == "CPM" else f"Rev {money(s['value'], 0)}"
            name = ("★ " if i == best else "") + s["name"]
            tags = ("best",) if i == best else (("even",) if i % 2 else ("odd",))
            self.tree.insert("", "end", iid=str(i), tags=tags, values=(
                name, s["mode"], s["tipo"], num_s(s["req"]), num_s(s["bids"]),
                num_s(s["wins"]), num_s(s["imps"]), valtxt, rate_s(m["bid"]),
                rate_s(m["win"]), rate_s(m["render"]), rate_s(m["fill"]),
                money(m["ecpm"]), rate_s(m["margin"])))
        if best is not None:
            self.banner.config(
                text=f"★ Más rentable: {self.sources[best]['name']} · "
                     f"eCPM Neto {money(ms[best]['ecpm'])}")
        else:
            self.banner.config(text="Agrega fuentes para ver el ranking.", fg=MUTED)
        if best is not None:
            self.banner.config(fg=SUCCESS)
        self._ms = ms
        self._draw_rank()

    def _draw_rank(self):
        c = self.rank
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100:
            return
        ms = getattr(self, "_ms", [])
        if not ms:
            c.create_text(w / 2, h / 2, text="Sin fuentes cargadas", font=FONT_SMALL,
                          fill=MUTED)
            return
        order = sorted(range(len(ms)), key=lambda i: ms[i]["ecpm"], reverse=True)
        top = ms[order[0]]["ecpm"] or 1
        n = len(order)
        row_h = min(34, (h - 4) / n)
        bar_h = max(10, row_h - 10)
        left, right = 128, 62
        for rank, i in enumerate(order):
            y = 2 + rank * row_h
            name = self.sources[i]["name"]
            name = name if len(name) <= 14 else name[:13] + "…"
            col = SUCCESS if rank == 0 else PRIMARY
            c.create_text(0, y + bar_h / 2 + 2, text=f"{rank + 1}. {name}", anchor="w",
                          font=FONT_B if rank == 0 else FONT, fill=TEXT)
            x0, x1 = left, max(left + 10, w - right)
            c.create_rectangle(x0, y, x1, y + bar_h, fill=TRACK, outline="")
            fw = (x1 - x0) * max(0.0, ms[i]["ecpm"]) / top
            if fw > 0:
                c.create_rectangle(x0, y, x0 + fw, y + bar_h, fill=col, outline="")
            c.create_text(x1 + 8, y + bar_h / 2 + 2, text=money(ms[i]["ecpm"]), anchor="w",
                          font=FONT_B, fill=col)

    def export_csv(self):
        if not self.sources:
            messagebox.showinfo("Exportar CSV", "No hay fuentes para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="comparador_fuentes.csv",
            filetypes=[("CSV", "*.csv"), ("Todos los archivos", "*.*")])
        if not path:
            return
        ms = [source_metrics(s) for s in self.sources]
        best = max(range(len(ms)), key=lambda i: ms[i]["ecpm"])
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(["Fuente", "Modo de pago", "Tipo", "Fee %", "Requests", "Bids",
                            "Wins", "Impresiones", "CPM / Revenue", "Bid Rate %",
                            "Win Rate %", "Render Rate %", "Fill Rate %", "Revenue Bruto",
                            "Revenue Neto", "eCPM Neto", "Margen %", "Más rentable"])
                for i, (s, m) in enumerate(zip(self.sources, ms)):
                    def r2(x):
                        return "" if x is None else f"{x:.2f}"
                    w.writerow([s["name"], s["mode"], s["tipo"], f"{s['fee']:.2f}",
                                int(s["req"]), int(s["bids"]), int(s["wins"]),
                                int(s["imps"]), f"{s['value']:.2f}", r2(m["bid"]),
                                r2(m["win"]), r2(m["render"]), r2(m["fill"]),
                                f"{m['gross']:.2f}", f"{m['net']:.2f}",
                                f"{m['ecpm']:.2f}", f"{m['margin']:.2f}",
                                "SI" if i == best else ""])
            messagebox.showinfo("Exportar CSV", f"Archivo guardado:\n{path}")
        except OSError as e:
            messagebox.showerror("Exportar CSV", f"No se pudo guardar el archivo:\n{e}")


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
        self.v_own = tk.StringVar()
        self.v_par = tk.StringVar()
        self.v_rown = tk.StringVar()
        self.v_rpar = tk.StringVar()
        self._sample_i = 0
        self._level = None
        self._build()
        for v in (self.v_own, self.v_par, self.v_rown, self.v_rpar):
            v.trace_add("write", self.recalc)
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
        spec = [("Impresiones propias", self.v_own, 0, 0),
                ("Impresiones Partner", self.v_par, 0, 1),
                ("Revenue propio ($, opcional)", self.v_rown, 1, 0),
                ("Revenue Partner ($, opcional)", self.v_rpar, 1, 1)]
        for txt, var, r, c in spec:
            fr, _, _ = field(g, txt, var)
            fr.grid(row=r, column=c, sticky="ew", padx=(0, 8) if c == 0 else 0,
                    pady=(0, 10))
        tk.Label(inner, text="Discrepancia % = (Partner − Propias) ÷ Propias × 100.\n"
                             "El semáforo usa el mayor valor absoluto entre impresiones y revenue.",
                 font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w", justify="left").pack(
            fill="x", pady=(0, 10))
        b = tk.Frame(inner, bg=CARD)
        b.pack(fill="x", pady=(4, 0))
        FlatButton(b, "Calcular", self.recalc).pack(side="left")
        FlatButton(b, "Cargar datos de prueba", self.load_sample,
                   style="secondary").pack(side="left", padx=8)
        FlatButton(b, "Limpiar", self.clear, style="ghost").pack(side="left")
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
        self.l_pct = tk.Label(txt, text="", font=FONT_B, fg=TEXT, bg=CARD, anchor="w")
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
        self.status.config(text=msg, fg=DANGER if error else MUTED)

    def recalc(self, *_):
        try:
            own = parse_num(self.v_own.get())
            par = parse_num(self.v_par.get())
            ro = parse_num(self.v_rown.get())
            rp = parse_num(self.v_rpar.get())
        except ValueError as e:
            self._reset(f"⚠ {e}", error=True)
            return
        if own is None or par is None:
            self._reset("Completa Impresiones propias y Partner para calcular.")
            return
        if own <= 0:
            self._reset("⚠ Las impresiones propias deben ser mayores a 0.", error=True)
            return

        diff = par - own
        pct = diff / own * 100
        lv_i = disc_level(pct)
        worst = abs(pct)
        worst_src = "impresiones"
        col_i = self.ON[lv_i]
        self.k_abs.set(f"{diff:+,.0f}", f"Propias {own:,.0f} vs Partner {par:,.0f}", col_i)
        self.k_pct.set(f"{pct:+.2f}%", "(Partner − Propias) ÷ Propias", col_i)

        if ro and rp is not None and ro > 0:
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
        self.status.config(text="✓ Cálculo actualizado", fg=SUCCESS)

    def load_sample(self):
        own, par, ro, rp = self.SAMPLES[self._sample_i % len(self.SAMPLES)]
        self._sample_i += 1
        self.v_own.set(own)
        self.v_par.set(par)
        self.v_rown.set(ro)
        self.v_rpar.set(rp)

    def clear(self):
        for v in (self.v_own, self.v_par, self.v_rown, self.v_rpar):
            v.set("")


# ───────────────────────────── Aplicación principal ─────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AdOps · Control Financiero de Publicidad Programática")
        self.geometry("1180x760")
        self.minsize(1050, 680)
        setup_style(self)
        self.price_type = tk.StringVar(value="Bruto")
        self._build_header()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(10, 14))
        self.tab_calc = CalcTab(self.nb, self)
        self.tab_cmp = CompareTab(self.nb, self)
        self.tab_disc = DiscTab(self.nb, self)
        self.nb.add(self.tab_calc, text="  Calculadora CPM / eCPM y Margen  ")
        self.nb.add(self.tab_cmp, text="  Comparador de Fuentes (eCPM y Embudo)  ")
        self.nb.add(self.tab_disc, text="  Control de Discrepancias  ")

        self.price_type.trace_add("write", self._on_price_type)

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
        self.menu.add_command(label="Limpiar todo", command=self.clear_all)

    def _popup_menu(self):
        b = self.btn_menu
        try:
            self.menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            self.menu.grab_release()

    def _on_price_type(self, *_):
        self.tab_calc.recalc()
        self.tab_cmp.sync_type()

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

#!/usr/bin/env python3
"""
BatesAI — Stock Market Analyzer
Professional technical analysis suite with Systematic Momentum Screener.
"""

import sys
import os
import json
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import numpy as np
import pandas as pd
import yfinance as yf

def set_app_name():
    """Try to set the macOS menu bar name."""
    if sys.platform == "darwin":
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            if bundle:
                info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if info:
                    info["CFBundleName"] = "Stock Analyzer"
                    info["CFBundleDisplayName"] = "Stock Analyzer"
        except ImportError:
            pass

# Add parent directory to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portfolio_manager import PortfolioManager
import recommendation_engine

class SearchableCombobox:
    def __init__(self, parent, values=None, width=30, **kwargs):
        self._values = values or []
        self.var = tk.StringVar()
        self.frame = tk.Frame(parent, bg="#1a1a2e")
        self.entry = ttk.Entry(self.frame, textvariable=self.var, width=width, **kwargs)
        self.entry.pack(side=tk.LEFT, padx=2)
        self.listbox = None
        self._popup_open = False
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", self._on_select)

    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"): return
        query = self.var.get().strip().upper()
        if not query:
            self._close_popup()
            return
        matches = [v for v in self._values if query in v.upper()][:20]
        if matches: self._show_popup(matches)
        else: self._close_popup()

    def _show_popup(self, matches):
        if self._popup_open and self.listbox:
            self.listbox.delete(0, tk.END)
        else:
            self._popup_open = True
            self.listbox = tk.Listbox(self.frame, bg="#16213e", fg="#e0e0e0",
                                       selectbackground="#0f3460", height=min(len(matches), 10),
                                       borderwidth=1, relief=tk.SOLID)
            self.listbox.place(x=0, y=self.entry.winfo_height() + 2, width=self.entry.winfo_width())
        for m in matches: self.listbox.insert(tk.END, m)

    def _close_popup(self, event=None):
        if self.listbox: self.listbox.destroy()
        self.listbox = None
        self._popup_open = False

    def _on_select(self, event=None):
        self._close_popup()
        return "break"

    def get(self):
        return self.var.get().strip().upper()

class IndicatorPanel:
    def __init__(self, parent, indicators, on_change):
        self.indicators = indicators
        self.on_change = on_change
        self.vars = {}
        self.frame = tk.Frame(parent, bg="#16213e")
        cols = 6
        for i, (key, label) in enumerate(indicators.items()):
            var = tk.BooleanVar(value=False)
            self.vars[key] = var
            cb = ttk.Checkbutton(self.frame, text=label, variable=var, command=self.on_change)
            cb.grid(row=i // cols, column=i % cols, sticky=tk.W, padx=12, pady=4)

    def get_active(self):
        return [k for k, v in self.vars.items() if v.get()]

class StockAnalyzerGUI:
    def __init__(self):
        set_app_name()
        try:
            self.pm = PortfolioManager(os.path.join(os.path.dirname(__file__), "portfolio.json"))
            self.root = tk.Tk()
            self.root.title("BatesAI — Stock Analyzer")
            self.root.geometry("1400x900")
            self.root.configure(bg="#1a1a2e")
            
            icon_path = os.path.join(os.path.dirname(__file__), "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_img)

            self._all_tickers = []
            self._load_ticker_list()
            self._rec_loading = False
            self._build_ui()
            # Defer initial chart update to ensure window shows up immediately
            self.root.after(100, self._update_charts)
            # Auto-backtest & refresh the recommendations tab on every launch
            self.root.after(400, self._refresh_recommendations)
        except Exception as e:
            print(f"STARTUP ERROR: {traceback.format_exc()}")

    def _load_ticker_list(self):
        common = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "TSLA", "BRK-B", "V", "JPM", "SPY", "QQQ", "DIA", "IWM", "BTC-USD"]
        self._all_tickers = sorted(set(common))

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#16213e", foreground="#e0e0e0", fieldbackground="#16213e", borderwidth=0, rowheight=25)
        style.configure("Treeview.Heading", background="#0f3460", foreground="#e0e0e0", borderwidth=0, font=("Helvetica", 10, "bold"))
        style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#0f3460", foreground="#e0e0e0", padding=[20, 8], font=("Helvetica", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#e94560")], foreground=[("selected", "white")])
        style.configure("Header.TLabel", background="#1a1a2e", foreground="#e94560", font=("Helvetica", 16, "bold"))
        style.configure("Subheader.TLabel", background="#1a1a2e", foreground="#a0a0a0", font=("Helvetica", 11))
        style.configure("TButton", background="#0f3460", foreground="white", borderwidth=0)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 0: Current Most Recommended Stocks (auto-refreshed on launch)
        self.rec_tab = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(self.rec_tab, text=" 💎 Top Recommendations ")
        self._build_recommendations_tab(self.rec_tab)

        # Tab 1: Analyzer
        self.chart_tab = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(self.chart_tab, text=" 📊 Chart Analyzer ")
        self._build_chart_tab(self.chart_tab)

        # Tab 2: Screener
        self.screener_tab = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(self.screener_tab, text=" 🎯 Systematic Screener ")
        self._build_screener_tab(self.screener_tab)

        # Tab 3: Log
        self.log_tab = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(self.log_tab, text=" 📝 System Log ")
        self._build_log_tab(self.log_tab)

    def _build_log_tab(self, parent):
        f = tk.Frame(parent, bg="#1a1a2e")
        f.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.log_text = tk.Text(f, bg="#0f0f1a", fg="#4ecca3", font=("Courier New", 11), relief=tk.FLAT, borderwidth=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_msg("System ready. Suite initialized.")

    def log_msg(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        def _app():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.root.update_idletasks()
        self.root.after(0, _app)

    def _build_recommendations_tab(self, parent):
        f = tk.Frame(parent, bg="#1a1a2e")
        f.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        header = tk.Frame(f, bg="#1a1a2e")
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="CURRENT MOST RECOMMENDED STOCKS", style="Header.TLabel").pack(side=tk.LEFT)
        self.rec_refresh_btn = ttk.Button(header, text="🔄 Re-run Backtest", command=self._refresh_recommendations)
        self.rec_refresh_btn.pack(side=tk.RIGHT)
        self.rec_status_label = ttk.Label(header, text="", style="Subheader.TLabel")
        self.rec_status_label.pack(side=tk.RIGHT, padx=12)

        ttk.Label(
            f, style="Subheader.TLabel",
            text="Recommendation Points (0-100): 100 = best deal in market history, 0 = guaranteed to tank. "
                 "Backtested & refreshed automatically every launch.",
        ).pack(fill=tk.X, pady=(0, 10))

        self.rec_progress = ttk.Progressbar(f, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.rec_progress.pack(fill=tk.X, pady=(0, 12))

        table_f = tk.Frame(f, bg="#16213e")
        table_f.pack(fill=tk.BOTH, expand=True)

        cols = ("rank", "ticker", "score", "price", "change", "momentum", "rsi", "vol", "bt", "drivers")
        headers = ["#", "Ticker", "Rec. Points", "Price", "Day", "12-1 Mom %",
                   "RSI", "Volatility %", "Backtest %", "Top Drivers"]
        widths = [40, 70, 110, 90, 70, 90, 60, 90, 90, 200]
        self.rec_tree = ttk.Treeview(table_f, columns=cols, show="headings")
        for c, h, w in zip(cols, headers, widths):
            self.rec_tree.heading(c, text=h)
            self.rec_tree.column(c, width=w, anchor="center")
        self.rec_tree.column("drivers", anchor="w")

        # Color rows by score band
        self.rec_tree.tag_configure("elite", foreground="#4ecca3")    # 80+
        self.rec_tree.tag_configure("strong", foreground="#9be8c4")   # 65-80
        self.rec_tree.tag_configure("fair", foreground="#e0e0e0")     # 50-65
        self.rec_tree.tag_configure("weak", foreground="#e9a445")     # 35-50
        self.rec_tree.tag_configure("avoid", foreground="#e94560")    # <35

        sb = ttk.Scrollbar(table_f, orient=tk.VERTICAL, command=self.rec_tree.yview)
        self.rec_tree.configure(yscroll=sb.set)
        self.rec_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_tree.bind("<Double-1>", self._on_rec_select)

    def _on_rec_select(self, event):
        sel = self.rec_tree.selection()
        if not sel:
            return
        ticker = self.rec_tree.item(sel[0], "values")[1]
        self.search_combo.var.set(ticker)
        self.notebook.select(self.chart_tab)
        self._update_charts()

    @staticmethod
    def _rec_tag(score):
        if score >= 80: return "elite"
        if score >= 65: return "strong"
        if score >= 50: return "fair"
        if score >= 35: return "weak"
        return "avoid"

    def _refresh_recommendations(self):
        if self._rec_loading:
            return
        self._rec_loading = True
        self.rec_refresh_btn.config(state="disabled")
        self.rec_status_label.config(text="Backtesting market…")
        self.rec_progress.configure(value=0)
        self.log_msg("Recommendations: backtesting universe for top 10 picks…")

        universe = recommendation_engine.DEFAULT_UNIVERSE
        cache_dir = os.path.join(os.path.dirname(__file__), "cache")

        def progress(msg):
            self.log_msg(msg)
            # Parse "(i/total)" to advance the progress bar
            try:
                frac = msg.split("(")[1].split(")")[0]
                i, total = frac.split("/")
                self.root.after(0, lambda v=int(int(i) / int(total) * 100): self.rec_progress.configure(value=v))
            except Exception:
                pass

        def worker():
            try:
                top = recommendation_engine.rank_recommendations(
                    universe=universe, top_n=10, period="2y",
                    cache_dir=cache_dir, log=progress)
                self.root.after(0, lambda: self._fill_rec_table(top))
                self.log_msg(f"Recommendations: top {len(top)} picks ready.")
            except Exception as e:
                self.log_msg(f"Recommendations ERROR: {e}")
            finally:
                self.root.after(0, self._rec_done)
        threading.Thread(target=worker, daemon=True).start()

    def _rec_done(self):
        self._rec_loading = False
        self.rec_refresh_btn.config(state="normal")
        self.rec_progress.configure(value=100)
        self.rec_status_label.config(text=f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    def _fill_rec_table(self, data):
        for i in self.rec_tree.get_children():
            self.rec_tree.delete(i)
        for idx, r in enumerate(data, 1):
            self.rec_tree.insert(
                "", "end",
                values=(idx, r["ticker"], f"{r['score']:.1f}", f"${r['price']:.2f}",
                        f"{r['daily_change']:+.2f}%", f"{r['momentum_12_1']:+.1f}",
                        f"{r['rsi']:.0f}", f"{r['annual_vol']:.0f}",
                        f"{r['strategy_return']:+.1f}", r["drivers"]),
                tags=(self._rec_tag(r["score"]),))

    def _build_chart_tab(self, parent):
        main = tk.Frame(parent, bg="#1a1a2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Header
        header = tk.Frame(main, bg="#1a1a2e")
        header.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(header, text="BATESAI — STOCK ANALYZER", style="Header.TLabel").pack(side=tk.LEFT)
        self.last_update_label = ttk.Label(header, text="", style="Subheader.TLabel")
        self.last_update_label.pack(side=tk.RIGHT)

        # Controls
        ctrl = tk.Frame(main, bg="#1a1a2e")
        ctrl.pack(fill=tk.X, pady=5)
        
        ttk.Label(ctrl, text="Ticker:").pack(side=tk.LEFT, padx=5)
        self.search_combo = SearchableCombobox(ctrl, values=self._all_tickers, width=12)
        self.search_combo.frame.pack(side=tk.LEFT)
        self.search_combo.var.set("SPY")
        self.search_combo.entry.bind("<Return>", lambda e: self._update_charts())
        
        ttk.Label(ctrl, text="View:").pack(side=tk.LEFT, padx=(15, 5))
        self.chart_type_var = tk.StringVar(value="Price")
        views = ["Price", "Price + Volume", "ATMS Strategy", "CFO Strategy", "RSI", "MACD", "Full Technical"]
        v_combo = ttk.Combobox(ctrl, textvariable=self.chart_type_var, values=views, width=16, state="readonly")
        v_combo.pack(side=tk.LEFT)
        v_combo.bind("<<ComboboxSelected>>", lambda e: self._update_charts())
        
        ttk.Label(ctrl, text="Style:").pack(side=tk.LEFT, padx=(15, 5))
        self.chart_style_var = tk.StringVar(value="Candlestick")
        s_combo = ttk.Combobox(ctrl, textvariable=self.chart_style_var, values=["Candlestick", "Line", "OHLC Bars", "Heikin-Ashi"], width=12, state="readonly")
        s_combo.pack(side=tk.LEFT)
        s_combo.bind("<<ComboboxSelected>>", lambda e: self._update_charts())

        ttk.Label(ctrl, text="Period:").pack(side=tk.LEFT, padx=(15, 5))
        self.period_var = tk.StringVar(value="1y")
        p_combo = ttk.Combobox(ctrl, textvariable=self.period_var, values=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], width=6, state="readonly")
        p_combo.pack(side=tk.LEFT)
        p_combo.bind("<<ComboboxSelected>>", lambda e: self._update_charts())

        # Indicators
        indicator_frame = tk.Frame(main, bg="#16213e")
        indicator_frame.pack(fill=tk.X, pady=10)
        indicators = {
            "sma_50": "SMA 50", "sma_200": "SMA 200", "ema_12": "EMA 12", "ema_26": "EMA 26",
            "vwap": "VWAP", "bbands": "Bollinger Bands", "ichimoku": "Ichimoku", "signals": "RSI Signals"
        }
        self.indicator_panel = IndicatorPanel(indicator_frame, indicators, self._update_charts)
        self.indicator_panel.frame.pack(fill=tk.X, padx=10, pady=5)

        # Chart Display
        self.chart_frame = tk.Frame(main, bg="#1a1a2e")
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
        self.canvases = {}

    def _build_screener_tab(self, parent):
        f = tk.Frame(parent, bg="#1a1a2e")
        f.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        header = tk.Frame(f, bg="#1a1a2e")
        header.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header, text="SYSTEMATIC MOMENTUM SCREENER", style="Header.TLabel").pack(side=tk.LEFT)
        
        btn_f = tk.Frame(header, bg="#1a1a2e")
        btn_f.pack(side=tk.RIGHT)
        self.run_quick_btn = ttk.Button(btn_f, text="⚡ Quick Rank (Top 20)", command=lambda: self._run_momentum_screener(quick=True))
        self.run_quick_btn.pack(side=tk.LEFT, padx=5)
        self.run_full_btn = ttk.Button(btn_f, text="🚀 Full Rank (S&P 100)", command=lambda: self._run_momentum_screener(quick=False))
        self.run_full_btn.pack(side=tk.LEFT, padx=5)
        
        self.screener_progress = ttk.Progressbar(f, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.screener_progress.pack(fill=tk.X, pady=(0, 20))
        
        table_f = tk.Frame(f, bg="#16213e")
        table_f.pack(fill=tk.BOTH, expand=True)
        
        cols = ("rank", "ticker", "momentum", "price", "change")
        self.screener_tree = ttk.Treeview(table_f, columns=cols, show="headings")
        headers = ["Rank", "Ticker", "12-1 Momentum %", "Current Price", "Daily Change"]
        for c, h in zip(cols, headers):
            self.screener_tree.heading(c, text=h)
            self.screener_tree.column(c, width=120, anchor="center")
        self.screener_tree.column("rank", width=60)
        
        sb = ttk.Scrollbar(table_f, orient=tk.VERTICAL, command=self.screener_tree.yview)
        self.screener_tree.configure(yscroll=sb.set)
        self.screener_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.screener_tree.bind("<Double-1>", self._on_screener_select)

    def _on_screener_select(self, event):
        sel = self.screener_tree.selection()
        if not sel: return
        ticker = self.screener_tree.item(sel[0], "values")[1]
        self.search_combo.var.set(ticker)
        self.notebook.select(0)
        self._update_charts()

    def _run_momentum_screener(self, quick=False):
        self.run_quick_btn.config(state="disabled")
        self.run_full_btn.config(state="disabled")
        self.log_msg(f"Initiating {'Quick' if quick else 'Full'} Market Scan...")
        def worker():
            try:
                all_tickers = ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "GOOG", "BRK-B", "TSLA", "UNH", "LLY", "V", "JPM", "XOM", "MA", "AVGO", "HD", "PG", "JNJ", "COST", "ADBE", "ABBV", "MRK", "CRM", "BAC", "CVX", "PEP", "WMT", "KO", "TMO", "NFLX", "CSCO", "ACN", "ABT", "LIN", "MCD", "DIS", "ORCL", "INTC", "WFC", "INTU", "AMD", "VZ", "PM", "IBM", "CMCSA", "TXN", "QCOM", "UNP", "AMGN", "GE", "CAT", "SPGI", "LOW", "HON", "ISRG", "AMAT", "BKNG", "PLD", "AXP", "RTX", "MDLZ", "TJX", "ADP", "SYK", "GILD", "VRTX", "C", "LRCX", "ADI", "ELV", "ETN", "MU", "T", "LMT", "BSX", "REGN", "MMC", "PANW", "CB", "PGR", "DE", "BMY", "CI", "BA", "MDT", "SCHW", "CDNS", "SNPS", "ICE", "WM", "ZTS", "KLAC", "DUK", "SO", "EOG", "SHW", "CL", "TGT", "MO"]
                tickers = all_tickers[:20] if quick else all_tickers
                results = []
                for i, t in enumerate(tickers):
                    self.log_msg(f"Processing {t} ({i+1}/{len(tickers)})...")
                    try:
                        d = yf.download(t, period="1y", interval="1d", progress=False, timeout=10)
                        if not d.empty and len(d) > 150:
                            c = d["Close"]
                            mom = (float(c.iloc[-22]) / float(c.iloc[0]) - 1) * 100
                            chg = (float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100
                            results.append({"t": t, "m": mom, "p": float(c.iloc[-1]), "c": chg})
                    except: pass
                    self.root.after(0, lambda v=int((i+1)/len(tickers)*100): self.screener_progress.configure(value=v))
                
                top = sorted(results, key=lambda x: x["m"], reverse=True)[:50]
                self.root.after(0, lambda: self._fill_table(top))
                self.log_msg("SUCCESS: Market ranking complete.")
            except Exception as e: self.log_msg(f"CRITICAL ERROR: {e}")
            finally:
                self.root.after(0, lambda: self.run_quick_btn.config(state="normal"))
                self.root.after(0, lambda: self.run_full_btn.config(state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def _fill_table(self, data):
        for i in self.screener_tree.get_children(): self.screener_tree.delete(i)
        for idx, item in enumerate(data, 1):
            self.screener_tree.insert("", "end", values=(idx, item["t"], f"{item['m']:.2f}%", f"${item['p']:.2f}", f"{item['c']:+.2f}%"))

    def _update_charts(self):
        ticker = self.search_combo.get() or "SPY"
        period = self.period_var.get()
        v_type = self.chart_type_var.get()
        style = self.chart_style_var.get()
        
        for w in self.chart_frame.winfo_children(): w.destroy()
        df = self.pm.get_historical_data(ticker, period)
        if df.empty: return

        fig = Figure(figsize=(10, 7), facecolor="#1a1a2e", dpi=100)
        
        if v_type == "Full Technical":
            gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.1)
            ax = fig.add_subplot(gs[0])
            ax_v = fig.add_subplot(gs[1], sharex=ax)
            ax_r = fig.add_subplot(gs[2], sharex=ax)
            self._draw_main_plot(ax, df, style)
            self._draw_volume(ax_v, df)
            self._draw_rsi(ax_r, df)
        elif v_type == "Price + Volume":
            gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
            ax = fig.add_subplot(gs[0])
            ax_v = fig.add_subplot(gs[1], sharex=ax)
            self._draw_main_plot(ax, df, style)
            self._draw_volume(ax_v, df)
        elif v_type == "ATMS Strategy":
            ax = fig.add_subplot(111)
            self._draw_main_plot(ax, df, style)
            self._draw_atms_logic(ax, df)
        elif v_type == "CFO Strategy":
            ax = fig.add_subplot(111)
            self._draw_main_plot(ax, df, style)
            self._draw_cfo_logic(ax, df)
        elif v_type == "RSI":
            ax = fig.add_subplot(111)
            self._draw_rsi(ax, df)
        elif v_type == "MACD":
            ax = fig.add_subplot(111)
            self._draw_macd(ax, df)
        else:
            ax = fig.add_subplot(111)
            self._draw_main_plot(ax, df, style)
            self._draw_overlays(ax, df)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.last_update_label.config(text=f"{ticker} | {period} | {datetime.now().strftime('%H:%M:%S')}")

    def _draw_main_plot(self, ax, df, style):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white", labelsize=8)
        for s in ax.spines.values(): s.set_color("#333")
        ax.grid(True, alpha=0.1, color="white")
        
        if style == "Line":
            ax.plot(df.index, df["Close"], color="#e94560", linewidth=1.5)
        elif style == "Heikin-Ashi":
            self._draw_heikin(ax, df)
        else:
            self._draw_candles(ax, df, style == "OHLC Bars")

    def _draw_candles(self, ax, df, ohlc=False):
        dates = mdates.date2num(df.index)
        for i in range(len(df)):
            o, h, l, c = df["Open"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i], df["Close"].iloc[i]
            color = "#4ecca3" if c >= o else "#e94560"
            if ohlc:
                ax.plot([dates[i], dates[i]], [l, h], color=color, lw=1)
                ax.plot([dates[i]-0.3, dates[i]], [o, o], color=color, lw=1)
                ax.plot([dates[i], dates[i]+0.3], [c, c], color=color, lw=1)
            else:
                ax.plot([dates[i], dates[i]], [l, h], color=color, lw=1)
                ax.add_patch(mpatches.Rectangle((dates[i]-0.3, min(o,c)), 0.6, abs(o-c), facecolor=color))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m'))

    def _draw_heikin(self, ax, df):
        ha = df.copy()
        ha["Close"] = (df.Open + df.High + df.Low + df.Close) / 4
        ha.iloc[0, 0] = (df.Open.iloc[0] + df.Close.iloc[0]) / 2
        for i in range(1, len(ha)): ha.iloc[i, 0] = (ha.Open.iloc[i-1] + ha.Close.iloc[i-1]) / 2
        ha["High"] = ha[["High", "Open", "Close"]].max(axis=1)
        ha["Low"] = ha[["Low", "Open", "Close"]].min(axis=1)
        self._draw_candles(ax, ha)

    def _draw_overlays(self, ax, df):
        active = self.indicator_panel.get_active()
        close = df["Close"]
        if "sma_50" in active: ax.plot(df.index, close.rolling(50).mean(), color="#00bcd4", lw=1, label="SMA 50")
        if "sma_200" in active: ax.plot(df.index, close.rolling(200).mean(), color="#ffd700", lw=1, label="SMA 200")
        if "bbands" in active:
            m = close.rolling(20).mean()
            s = close.rolling(20).std()
            ax.plot(df.index, m+2*s, color="#4ecca3", lw=0.5, ls="--")
            ax.plot(df.index, m-2*s, color="#4ecca3", lw=0.5, ls="--")
            ax.fill_between(df.index, m-2*s, m+2*s, color="#4ecca3", alpha=0.05)
        if "signals" in active:
            self._draw_rsi_signals(ax, df)
        if active: ax.legend(fontsize=7, facecolor="#1a1a2e", labelcolor="white")

    def _draw_atms_logic(self, ax, df):
        close = df["Close"]
        n, fast, slow = 10, 2, 30
        er = (close - close.shift(n)).abs() / close.diff().abs().rolling(n).sum()
        sc = (er * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1))**2
        kama = [close.iloc[0]]
        for i in range(1, len(df)): kama.append(kama[-1] + sc.iloc[i] * (close.iloc[i] - kama[-1]))
        kama = pd.Series(kama, index=df.index)
        ax.plot(df.index, kama, color="#00bcd4", lw=2, label="ATMS Adaptive MA")
        ax.fill_between(df.index, kama*0.98, kama*1.02, color="#00bcd4", alpha=0.1)
        ax.legend()

    def _draw_cfo_logic(self, ax, df):
        s50 = df["Close"].rolling(50).mean()
        s200 = df["Close"].rolling(200).mean()
        ax.plot(df.index, s50, color="#4ecca3", lw=1.5, label="50 SMA")
        ax.plot(df.index, s200, color="#ffd700", lw=1.5, label="200 SMA")
        cross = s50 - s200
        gold = (cross.shift(1) < 0) & (cross > 0)
        death = (cross.shift(1) > 0) & (cross < 0)
        ax.scatter(df.index[gold], s50[gold], marker="^", color="#4ecca3", s=100, label="GOLDEN CROSS")
        ax.scatter(df.index[death], s50[death], marker="v", color="#e94560", s=100, label="DEATH CROSS")
        ax.legend()

    def _draw_rsi(self, ax, df):
        ax.set_facecolor("#16213e")
        d = df["Close"].diff()
        g, l = d.where(d > 0, 0).rolling(14).mean(), (-d.where(d < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + g/l))
        ax.plot(df.index, rsi, color="#e94560")
        ax.axhline(70, color="#ff6b6b", ls="--", alpha=0.5)
        ax.axhline(30, color="#4ecca3", ls="--", alpha=0.5)
        ax.set_ylim(0, 100)
        ax.set_ylabel("RSI")

    def _draw_macd(self, ax, df):
        ax.set_facecolor("#16213e")
        c = df["Close"]
        e12, e26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
        m = e12 - e26
        s = m.ewm(span=9).mean()
        ax.plot(df.index, m, color="#e94560", label="MACD")
        ax.plot(df.index, s, color="#4ecca3", label="Signal")
        ax.bar(df.index, m-s, color="gray", alpha=0.3)
        ax.legend(fontsize=7)

    def _draw_volume(self, ax, df):
        ax.set_facecolor("#16213e")
        colors = ["#4ecca3" if c >= o else "#e94560" for o,c in zip(df.Open, df.Close)]
        ax.bar(df.index, df.Volume, color=colors, alpha=0.5)
        ax.set_ylabel("Vol")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = StockAnalyzerGUI()
    app.run()

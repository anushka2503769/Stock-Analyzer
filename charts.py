"""
charts.py — Generates all matplotlib / seaborn charts and saves them as PNGs.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import warnings
warnings.filterwarnings("ignore")

# ─── COLOUR PALETTE ──────────────────────────────────────────────────────────
DARK_BG    = "#0D1117"
PANEL_BG   = "#161B22"
ACCENT1    = "#00D4FF"   # cyan
ACCENT2    = "#7B61FF"   # violet
ACCENT3    = "#00E676"   # green
ACCENT4    = "#FF6B6B"   # red
ACCENT5    = "#FFD600"   # gold
GRID_COL   = "#21262D"
TEXT_LIGHT = "#E6EDF3"
TEXT_DIM   = "#8B949E"

def _style():
    """Apply dark theme globally."""
    plt.rcParams.update({
        "figure.facecolor":  DARK_BG,
        "axes.facecolor":    PANEL_BG,
        "axes.edgecolor":    GRID_COL,
        "axes.labelcolor":   TEXT_LIGHT,
        "axes.titlecolor":   TEXT_LIGHT,
        "xtick.color":       TEXT_DIM,
        "ytick.color":       TEXT_DIM,
        "grid.color":        GRID_COL,
        "grid.linestyle":    "--",
        "grid.linewidth":    0.5,
        "text.color":        TEXT_LIGHT,
        "font.family":       "DejaVu Sans",
        "legend.facecolor":  PANEL_BG,
        "legend.edgecolor":  GRID_COL,
        "legend.labelcolor": TEXT_LIGHT,
    })

_style()


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────

def chart_price_history(data, out_dir, ticker):
    pd_ = data["price_data"]
    if pd_.get("hist_1y") is None or pd_["hist_1y"].empty:
        return None

    hist = pd_["hist_1y"]
    close = hist["Close"]
    dates = close.index

    fig, axes = plt.subplots(4, 1, figsize=(14, 16),
                             gridspec_kw={"height_ratios": [4, 1.2, 1.2, 1.2]})
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"{ticker} — Price & Technicals (1Y)", color=TEXT_LIGHT,
                 fontsize=15, fontweight="bold", y=0.99)

    ax = axes[0]
    ax.fill_between(dates, close, alpha=0.12, color=ACCENT1)
    ax.plot(dates, close, color=ACCENT1, linewidth=1.5, label="Close")

    if pd_.get("ma50") is not None:
        ax.plot(dates, pd_["ma50"],  color=ACCENT5, linewidth=1, linestyle="--", label="MA50")
    if pd_.get("ma200") is not None:
        ax.plot(dates, pd_["ma200"], color=ACCENT2, linewidth=1, linestyle="--", label="MA200")
    if pd_.get("bb_upper") is not None:
        ax.fill_between(dates, pd_["bb_lower"], pd_["bb_upper"],
                        alpha=0.08, color=ACCENT5, label="Bollinger Bands")
        ax.plot(dates, pd_["bb_upper"], color=ACCENT5, linewidth=0.6, alpha=0.5)
        ax.plot(dates, pd_["bb_lower"], color=ACCENT5, linewidth=0.6, alpha=0.5)

    ax.set_ylabel("Price (USD)", fontsize=9)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.4)

    # Volume
    ax2 = axes[1]
    vol = hist["Volume"]
    colors = [ACCENT3 if c >= o else ACCENT4
              for c, o in zip(hist["Close"], hist["Open"])]
    ax2.bar(dates, vol, color=colors, alpha=0.7, width=0.8)
    if pd_.get("vol_ma20") is not None:
        ax2.plot(dates, pd_["vol_ma20"], color=ACCENT5, linewidth=1)
    ax2.set_ylabel("Volume", fontsize=9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e6:.0f}M"))
    ax2.grid(True, alpha=0.3)

    # RSI
    ax3 = axes[2]
    if pd_.get("rsi") is not None:
        rsi = pd_["rsi"]
        ax3.plot(dates, rsi, color=ACCENT2, linewidth=1.2)
        ax3.axhline(70, color=ACCENT4, linewidth=0.8, linestyle="--", alpha=0.8)
        ax3.axhline(30, color=ACCENT3, linewidth=0.8, linestyle="--", alpha=0.8)
        ax3.fill_between(dates, rsi, 70, where=(rsi >= 70), color=ACCENT4, alpha=0.2)
        ax3.fill_between(dates, rsi, 30, where=(rsi <= 30), color=ACCENT3, alpha=0.2)
        ax3.set_ylim(0, 100)
        ax3.set_ylabel("RSI (14)", fontsize=9)
        ax3.text(dates[-1], 72, "Overbought", color=ACCENT4, fontsize=7, va="bottom")
        ax3.text(dates[-1], 28, "Oversold",   color=ACCENT3, fontsize=7, va="top")
    ax3.grid(True, alpha=0.3)

    # MACD
    ax4 = axes[3]
    if pd_.get("macd") is not None:
        ax4.plot(dates, pd_["macd"],        color=ACCENT1, linewidth=1.2, label="MACD")
        ax4.plot(dates, pd_["macd_signal"], color=ACCENT5, linewidth=1.0, label="Signal")
        hist_vals = pd_["macd_hist"]
        ax4.bar(dates, hist_vals, color=[ACCENT3 if v >= 0 else ACCENT4 for v in hist_vals],
                alpha=0.6, width=0.8, label="Histogram")
        ax4.axhline(0, color=TEXT_DIM, linewidth=0.5)
        ax4.legend(loc="upper left", fontsize=7)
        ax4.set_ylabel("MACD", fontsize=9)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.98])
    path = os.path.join(out_dir, f"{ticker}_price_technicals.png")
    save(fig, path)
    return path


def chart_5y_price(data, out_dir, ticker):
    pd_ = data["price_data"]
    hist = pd_.get("hist_5y")
    if hist is None or hist.empty:
        return None

    close = hist["Close"]
    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor(DARK_BG)

    ax.fill_between(close.index, close, alpha=0.15, color=ACCENT2)
    ax.plot(close.index, close, color=ACCENT2, linewidth=1.8)

    # Annotate min/max
    idx_max = close.idxmax(); idx_min = close.idxmin()
    ax.annotate(f"${close[idx_max]:.0f}", xy=(idx_max, close[idx_max]),
                xytext=(0, 12), textcoords="offset points",
                color=ACCENT3, fontsize=8, arrowprops=dict(arrowstyle="-", color=ACCENT3))
    ax.annotate(f"${close[idx_min]:.0f}", xy=(idx_min, close[idx_min]),
                xytext=(0, -18), textcoords="offset points",
                color=ACCENT4, fontsize=8, arrowprops=dict(arrowstyle="-", color=ACCENT4))

    ax.set_title(f"{ticker} — 5-Year Price History", fontsize=13, fontweight="bold")
    ax.set_ylabel("Price (USD)")
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    path = os.path.join(out_dir, f"{ticker}_5y_price.png")
    save(fig, path)
    return path


def chart_valuation_radar(data, out_dir, ticker):
    val = data["valuation"]

    # Normalise key ratios to 0-100 score (inverted where lower=better)
    def score(val_, low, high, invert=False):
        if val_ is None:
            return 50
        v = max(low, min(high, val_))
        s = (v - low) / (high - low) * 100
        return 100 - s if invert else s

    categories = ["P/E", "P/B", "P/S", "EV/EBITDA", "PEG", "Div Yield"]
    raw = [
        val.get("trailingPE"),
        val.get("priceToBook"),
        val.get("priceToSalesTrailing12Months"),
        val.get("enterpriseToEbitda"),
        val.get("pegRatio"),
        (val.get("dividendYield") or 0) * 100,
    ]
    scores = [
        score(raw[0], 5, 60,  invert=True),
        score(raw[1], 0.5, 15, invert=True),
        score(raw[2], 0.5, 20, invert=True),
        score(raw[3], 2, 30,  invert=True),
        score(raw[4], 0, 4,   invert=True),
        score(raw[5], 0, 6,   invert=False),
    ]

    N = len(categories)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    scores_plot = scores + scores[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(PANEL_BG)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color=TEXT_LIGHT, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], color=TEXT_DIM, fontsize=7)
    ax.grid(color=GRID_COL, linewidth=0.7)

    ax.plot(angles, scores_plot, color=ACCENT1, linewidth=2)
    ax.fill(angles, scores_plot, color=ACCENT1, alpha=0.25)

    ax.set_title(f"{ticker} — Valuation Scorecard\n(100 = most attractive)", 
                 color=TEXT_LIGHT, fontsize=12, fontweight="bold", pad=20)

    # Raw values annotation
    for i, (cat, val_, ang) in enumerate(zip(categories, raw, angles[:-1])):
        if val_ is not None:
            label = f"{val_:.2f}" if cat != "Div Yield" else f"{val_:.2f}%"
            ax.annotate(label, xy=(ang, scores[i]), xytext=(ang, scores[i]+12),
                        color=ACCENT5, fontsize=7.5, ha="center")

    plt.tight_layout()
    path = os.path.join(out_dir, f"{ticker}_valuation_radar.png")
    save(fig, path)
    return path


def chart_financial_health(data, out_dir, ticker):
    h = data["health"]
    info = data["info"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"{ticker} — Financial Health Overview", color=TEXT_LIGHT,
                 fontsize=13, fontweight="bold")

    # ── Liquidity gauges ──
    ax = axes[0]
    ax.set_facecolor(PANEL_BG)
    metrics = ["Current\nRatio", "Quick\nRatio"]
    vals    = [h.get("currentRatio"), h.get("quickRatio")]
    tholds  = [1.5, 1.0]
    colors  = [ACCENT3 if (v or 0) >= t else ACCENT4 for v, t in zip(vals, tholds)]
    bars = ax.bar(metrics, [v or 0 for v in vals], color=colors, width=0.4, alpha=0.85)
    for bar, val_ in zip(bars, vals):
        if val_:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                    f"{val_:.2f}x", ha="center", fontsize=11, fontweight="bold", color=TEXT_LIGHT)
    ax.axhline(1.0, color=ACCENT4, linewidth=1, linestyle="--", alpha=0.7, label="Min healthy")
    ax.axhline(1.5, color=ACCENT3, linewidth=1, linestyle="--", alpha=0.7, label="Ideal")
    ax.set_title("Liquidity Ratios", color=TEXT_LIGHT, fontsize=10)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # ── Margin waterfall ──
    ax2 = axes[1]
    ax2.set_facecolor(PANEL_BG)
    margin_names  = ["Gross\nMargin", "Operating\nMargin", "Net\nMargin", "EBITDA\nMargin"]
    margin_vals   = [
        (h.get("grossProfits") or 0) / (info.get("totalRevenue") or 1) * 100
        if info.get("totalRevenue") else None,
        (info.get("operatingMargins") or 0) * 100,
        (info.get("profitMargins")    or 0) * 100,
        (info.get("ebitdaMargins")    or 0) * 100,
    ]
    mv = [v or 0 for v in margin_vals]
    colors2 = [ACCENT3 if v >= 15 else ACCENT5 if v >= 5 else ACCENT4 for v in mv]
    bars2 = ax2.bar(margin_names, mv, color=colors2, width=0.4, alpha=0.85)
    for bar, v in zip(bars2, mv):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.5, f"{v:.1f}%",
                 ha="center", fontsize=10, fontweight="bold", color=TEXT_LIGHT)
    ax2.set_title("Profit Margins", color=TEXT_LIGHT, fontsize=10)
    ax2.set_ylabel("%")
    ax2.grid(True, alpha=0.3)

    # ── Debt overview ──
    ax3 = axes[2]
    ax3.set_facecolor(PANEL_BG)
    debt = h.get("totalDebt") or 0
    cash = h.get("totalCash") or 0
    net_debt = debt - cash

    categories_ = ["Total Debt", "Total Cash", "Net Debt"]
    vals_       = [debt/1e9, cash/1e9, net_debt/1e9]
    clrs        = [ACCENT4, ACCENT3, ACCENT4 if net_debt > 0 else ACCENT3]
    bars3 = ax3.bar(categories_, vals_, color=clrs, width=0.4, alpha=0.85)
    for bar, v in zip(bars3, vals_):
        ax3.text(bar.get_x() + bar.get_width()/2,
                 max(bar.get_height(), 0) + 0.1,
                 f"${v:.1f}B", ha="center", fontsize=10, fontweight="bold", color=TEXT_LIGHT)
    ax3.set_title("Debt vs Cash (Billions)", color=TEXT_LIGHT, fontsize=10)
    ax3.set_ylabel("USD Billion")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(out_dir, f"{ticker}_financial_health.png")
    save(fig, path)
    return path


def chart_revenue_earnings(data, out_dir, ticker):
    g = data["growth"]
    rev_hist = g.get("revenue_history")
    ni_hist  = g.get("net_income_history")

    if rev_hist is None and ni_hist is None:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"{ticker} — Revenue & Earnings History", color=TEXT_LIGHT,
                 fontsize=13, fontweight="bold")

    def _bar_series(ax, series, label, color, ylabel):
        if series is None or series.empty:
            ax.text(0.5, 0.5, "Data N/A", ha="center", va="center",
                    transform=ax.transAxes, color=TEXT_DIM)
            return
        series = series.sort_index()
        years = [str(d.year) for d in series.index]
        vals  = series.values / 1e9
        bars = ax.bar(years, vals, color=color, alpha=0.8, width=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + abs(vals).max() * 0.01,
                    f"${v:.1f}B", ha="center", fontsize=9, color=TEXT_LIGHT)
        # YoY growth labels
        for i in range(1, len(vals)):
            if vals[i-1] != 0:
                g_ = (vals[i] / vals[i-1] - 1) * 100
                ypos = max(vals[i], 0) + abs(vals).max() * 0.06
                ax.text(i, ypos, f"{g_:+.1f}%", ha="center", fontsize=8, color=ACCENT5)
        ax.set_title(label, color=TEXT_LIGHT, fontsize=10)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)

    _bar_series(axes[0], rev_hist, "Annual Revenue",    ACCENT1, "USD Billion")
    _bar_series(axes[1], ni_hist,  "Net Income / Loss", ACCENT3, "USD Billion")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(out_dir, f"{ticker}_revenue_earnings.png")
    save(fig, path)
    return path


def chart_returns_comparison(data, out_dir, ticker):
    pd_ = data["price_data"]
    if pd_.get("hist_1y") is None:
        return None

    returns = {
        "1W":  pd_.get("return_1w"),
        "1M":  pd_.get("return_1m"),
        "6M":  pd_.get("return_6m"),
        "1Y":  pd_.get("return_1y"),
    }
    labels = [k for k, v in returns.items() if v is not None]
    vals   = [returns[k] for k in labels]

    if not labels:
        return None

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(DARK_BG)
    colors = [ACCENT3 if v >= 0 else ACCENT4 for v in vals]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, width=0.45)
    for bar, v in zip(bars, vals):
        ypos = bar.get_height() + (0.3 if v >= 0 else -1.5)
        ax.text(bar.get_x() + bar.get_width()/2, ypos,
                f"{v:+.1f}%", ha="center", fontsize=11, fontweight="bold", color=TEXT_LIGHT)
    ax.axhline(0, color=TEXT_DIM, linewidth=0.8)
    ax.set_title(f"{ticker} — Price Returns by Period", color=TEXT_LIGHT,
                 fontsize=12, fontweight="bold")
    ax.set_ylabel("Return (%)")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    path = os.path.join(out_dir, f"{ticker}_returns.png")
    save(fig, path)
    return path


def chart_sentiment(data, out_dir, ticker):
    sent = data["sentiment"]
    articles = sent.get("articles", [])
    if not articles:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"{ticker} — News Sentiment Analysis", color=TEXT_LIGHT,
                 fontsize=13, fontweight="bold")

    # Pie chart
    ax1 = axes[0]
    ax1.set_facecolor(PANEL_BG)
    labels_ = ["Positive", "Neutral", "Negative"]
    sizes_  = [sent["positive_pct"], sent["neutral_pct"], sent["negative_pct"]]
    colors_ = [ACCENT3, ACCENT5, ACCENT4]
    sizes_  = [max(s, 0) for s in sizes_]
    if sum(sizes_) > 0:
        wedges, texts, autotexts = ax1.pie(
            sizes_, labels=labels_, colors=colors_,
            autopct="%1.0f%%", startangle=90,
            textprops={"color": TEXT_LIGHT, "fontsize": 10},
            wedgeprops={"edgecolor": DARK_BG, "linewidth": 2},
        )
        for at in autotexts:
            at.set_color(DARK_BG)
            at.set_fontweight("bold")
    ax1.set_title("Sentiment Distribution", color=TEXT_LIGHT, fontsize=11)

    # Compound scores timeline
    ax2 = axes[1]
    ax2.set_facecolor(PANEL_BG)
    scores   = [a["compound"] for a in articles]
    x_labels = [f"#{i+1}" for i in range(len(scores))]
    bar_cols = [ACCENT3 if s >= 0.05 else ACCENT4 if s <= -0.05 else ACCENT5 for s in scores]
    ax2.bar(x_labels, scores, color=bar_cols, alpha=0.85)
    ax2.axhline(0, color=TEXT_DIM, linewidth=0.8)
    ax2.axhline(0.05,  color=ACCENT3, linewidth=0.7, linestyle="--", alpha=0.5)
    ax2.axhline(-0.05, color=ACCENT4, linewidth=0.7, linestyle="--", alpha=0.5)
    ax2.set_ylim(-1, 1)
    ax2.set_title(f"VADER Compound Score — Recent Headlines\nAvg: {sent['avg_compound']:.3f} ({sent['overall']})",
                  color=TEXT_LIGHT, fontsize=10)
    ax2.set_ylabel("Compound Score")
    ax2.set_xlabel("Article #")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(out_dir, f"{ticker}_sentiment.png")
    save(fig, path)
    return path


def chart_analyst_vs_price(data, out_dir, ticker):
    dcf_ = data["dcf"]
    val  = data["valuation"]
    current = val.get("current_price")
    if not current:
        return None

    targets = {
        "Current\nPrice":   current,
        "Analyst\nLow":     dcf_.get("target_low"),
        "Analyst\nMean":    dcf_.get("target_mean"),
        "Analyst\nHigh":    dcf_.get("target_high"),
        "DCF\nIntrinsic":   dcf_.get("dcf_intrinsic"),
        "Graham\nNumber":   val.get("graham_number"),
    }

    labels = [k for k, v in targets.items() if v is not None]
    vals   = [targets[k] for k in labels]

    if len(vals) < 2:
        return None

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(DARK_BG)

    colors = []
    for k, v in zip(labels, vals):
        if "Current" in k:
            colors.append(ACCENT1)
        elif v > current:
            colors.append(ACCENT3)
        else:
            colors.append(ACCENT4)

    bars = ax.bar(labels, vals, color=colors, alpha=0.85, width=0.45)
    ax.axhline(current, color=ACCENT1, linewidth=1.5, linestyle="--", alpha=0.8, label=f"Current ${current:.2f}")

    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + current * 0.01,
                f"${v:.2f}", ha="center", fontsize=10, fontweight="bold", color=TEXT_LIGHT)

    ax.set_title(f"{ticker} — Price Targets vs Valuation Models", color=TEXT_LIGHT,
                 fontsize=12, fontweight="bold")
    ax.set_ylabel("Price (USD)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    path = os.path.join(out_dir, f"{ticker}_price_targets.png")
    save(fig, path)
    return path


def chart_scorecard(data, out_dir, ticker):
    """Heatmap-style scorecard of all key metrics."""
    h = data["health"]
    val = data["valuation"]
    g = data["growth"]
    pd_ = data["price_data"]
    info = data["info"]

    def _score_cell(label, value, low_good, high_bad, unit="", invert=False, neutral_range=None):
        if value is None:
            return label, "N/A", TEXT_DIM
        display = f"{value:.2f}{unit}"
        if invert:
            color = ACCENT3 if value <= low_good else ACCENT4 if value >= high_bad else ACCENT5
        else:
            if neutral_range:
                color = ACCENT3 if neutral_range[0] <= value <= neutral_range[1] else ACCENT4
            else:
                color = ACCENT3 if value >= low_good else ACCENT4 if value <= high_bad else ACCENT5
        return label, display, color

    cells = [
        _score_cell("P/E Ratio",       val.get("trailingPE"), 15, 35, invert=True),
        _score_cell("Forward P/E",     val.get("forwardPE"), 12, 30, invert=True),
        _score_cell("P/B Ratio",       val.get("priceToBook"), 1, 5, invert=True),
        _score_cell("EV/EBITDA",       val.get("enterpriseToEbitda"), 8, 20, invert=True),
        _score_cell("PEG Ratio",       val.get("pegRatio"), 1, 2, invert=True),
        _score_cell("Dividend Yield",  (val.get("dividendYield") or 0)*100, 2.5, 0.5, unit="%"),
        _score_cell("Current Ratio",   h.get("currentRatio"), 1.5, 1.0),
        _score_cell("Quick Ratio",     h.get("quickRatio"), 1.0, 0.5),
        _score_cell("Debt/Equity",     (h.get("debtToEquity") or 0)/100 if h.get("debtToEquity") else None, 0.5, 2.0, invert=True),
        _score_cell("ROE",             (info.get("returnOnEquity") or 0)*100, 15, 5, unit="%"),
        _score_cell("ROA",             (info.get("returnOnAssets") or 0)*100, 5, 2, unit="%"),
        _score_cell("Net Margin",      (info.get("profitMargins") or 0)*100, 10, 3, unit="%"),
        _score_cell("Gross Margin",    (info.get("grossMargins") or 0)*100, 30, 10, unit="%"),
        _score_cell("Op Margin",       (info.get("operatingMargins") or 0)*100, 15, 5, unit="%"),
        _score_cell("Revenue Growth",  (g.get("revenueGrowth") or 0)*100, 10, 3, unit="%"),
        _score_cell("RSI",             pd_.get("rsi", pd.Series()).iloc[-1] if isinstance(pd_.get("rsi"), pd.Series) and len(pd_.get("rsi", [])) > 0 else None, 50, 70, neutral_range=(40, 60)),
        _score_cell("Sharpe Ratio",    pd_.get("sharpe"), 1, 0),
        _score_cell("Altman Z",        h.get("altman_z"), 2.99, 1.81),
        _score_cell("Piotroski F",     h.get("piotroski"), 7, 3),
        _score_cell("Max Drawdown",    pd_.get("max_drawdown"), -10, -30, unit="%", invert=True),
    ]

    n = len(cells)
    cols = 4
    rows = (n + cols - 1) // cols

    fig, ax = plt.subplots(figsize=(14, rows * 1.4))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.axis("off")
    ax.set_title(f"{ticker} — Comprehensive Metric Scorecard",
                 color=TEXT_LIGHT, fontsize=13, fontweight="bold", pad=12)

    cell_w = 1 / cols
    cell_h = 1 / rows

    for i, (label, display, color) in enumerate(cells):
        col = i % cols
        row = i // cols
        x = col * cell_w + 0.005
        y = 1 - (row + 1) * cell_h + 0.005
        w = cell_w - 0.01
        h_ = cell_h - 0.01

        rect = FancyBboxPatch((x, y), w, h_, transform=ax.transAxes,
                              boxstyle="round,pad=0.01", linewidth=0,
                              facecolor=PANEL_BG, zorder=1)
        ax.add_patch(rect)

        # colour strip on left
        strip = FancyBboxPatch((x, y), 0.008, h_, transform=ax.transAxes,
                               boxstyle="round,pad=0", linewidth=0,
                               facecolor=color, zorder=2)
        ax.add_patch(strip)

        ax.text(x + 0.015, y + h_ * 0.62, label,
                transform=ax.transAxes, fontsize=8, color=TEXT_DIM, va="center")
        ax.text(x + 0.015, y + h_ * 0.28, display,
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=TEXT_LIGHT, va="center")

    path = os.path.join(out_dir, f"{ticker}_scorecard.png")
    save(fig, path)
    return path


def generate_all_charts(data, out_dir):
    ticker = data["ticker"]
    charts = {}
    os.makedirs(out_dir, exist_ok=True)

    charts["price_technicals"] = chart_price_history(data, out_dir, ticker)
    charts["5y_price"]         = chart_5y_price(data, out_dir, ticker)
    charts["valuation_radar"]  = chart_valuation_radar(data, out_dir, ticker)
    charts["financial_health"] = chart_financial_health(data, out_dir, ticker)
    charts["revenue_earnings"] = chart_revenue_earnings(data, out_dir, ticker)
    charts["returns"]          = chart_returns_comparison(data, out_dir, ticker)
    charts["sentiment"]        = chart_sentiment(data, out_dir, ticker)
    charts["price_targets"]    = chart_analyst_vs_price(data, out_dir, ticker)
    charts["scorecard"]        = chart_scorecard(data, out_dir, ticker)

    return {k: v for k, v in charts.items() if v is not None}

"""
conclusion.py — Calls the Anthropic API to write a plain-English investment summary.
Falls back to a rule-based summary if the API is unavailable.
"""

import os
import requests
import json


def _fmt(val, suffix="", prefix="", decimals=2, pct=False, billions=False):
    if val is None:
        return "N/A"
    if billions:
        return f"{prefix}{val/1e9:.1f}B{suffix}"
    if pct:
        return f"{val*100:.1f}%"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def build_conclusion(data: dict) -> str:
    """Return a plain-English paragraph summarising the full analysis."""
    ticker  = data["ticker"]
    info    = data["info"]
    val     = data["valuation"]
    h       = data["health"]
    g       = data["growth"]
    pd_     = data["price_data"]
    sent    = data["sentiment"]
    dcf_    = data["dcf"]

    # Build a compact JSON context for the LLM
    context = {
        "ticker": ticker,
        "company": info.get("longName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "current_price": val.get("current_price"),
        "market_cap_b": (info.get("marketCap") or 0) / 1e9,
        "pe_trailing": val.get("trailingPE"),
        "pe_forward": val.get("forwardPE"),
        "pb": val.get("priceToBook"),
        "ev_ebitda": val.get("enterpriseToEbitda"),
        "peg": val.get("pegRatio"),
        "dividend_yield_pct": (val.get("dividendYield") or 0) * 100,
        "dcf_intrinsic": dcf_.get("dcf_intrinsic"),
        "dcf_margin_safety_pct": dcf_.get("dcf_margin_safety"),
        "analyst_mean_target": dcf_.get("target_mean"),
        "analyst_upside_pct": dcf_.get("upside_mean"),
        "analyst_recommendation": dcf_.get("recommendation"),
        "graham_number": val.get("graham_number"),
        "current_ratio": h.get("currentRatio"),
        "quick_ratio": h.get("quickRatio"),
        "debt_to_equity": h.get("debtToEquity"),
        "debt_ebitda": h.get("debt_ebitda"),
        "net_debt_b": (h.get("net_debt") or 0) / 1e9,
        "altman_z": h.get("altman_z"),
        "piotroski_f": h.get("piotroski"),
        "roe_pct": (info.get("returnOnEquity") or 0) * 100,
        "roa_pct": (info.get("returnOnAssets") or 0) * 100,
        "gross_margin_pct": (info.get("grossMargins") or 0) * 100,
        "net_margin_pct": (info.get("profitMargins") or 0) * 100,
        "revenue_growth_pct": (g.get("revenueGrowth") or 0) * 100,
        "earnings_growth_pct": (g.get("earningsGrowth") or 0) * 100,
        "return_1y_pct": pd_.get("return_1y"),
        "return_6m_pct": pd_.get("return_6m"),
        "sharpe_ratio": pd_.get("sharpe"),
        "max_drawdown_pct": pd_.get("max_drawdown"),
        "annualised_vol_pct": pd_.get("annualised_vol"),
        "sentiment_overall": sent.get("overall"),
        "sentiment_avg_compound": sent.get("avg_compound"),
        "sentiment_positive_pct": sent.get("positive_pct"),
        "sentiment_negative_pct": sent.get("negative_pct"),
    }

    prompt = f"""You are a senior equity research analyst writing the concluding paragraph of a professional investment report for {context['company']} ({ticker}).

Here is the complete quantitative analysis data:
{json.dumps(context, indent=2)}

Write a single, densely informative paragraph (200-280 words) that:
1. Opens with a crisp verdict (bullish / bearish / neutral) with one-sentence rationale.
2. Highlights the 3-4 most important positives about this stock based on the data.
3. Highlights the 2-3 most significant risks or red flags.
4. Comments briefly on news sentiment accuracy and what it signals.
5. Closes with a plain-English conclusion about whether this stock appears overvalued, fairly valued, or undervalued based on DCF, Graham Number, and analyst targets.

Write in clear, professional but accessible English — avoid jargon where possible. Do NOT use bullet points. Do NOT use any markdown formatting. This is flowing prose only. Do not start with "In conclusion"."""

    # Try Anthropic API
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            result = resp.json()
            text = result["content"][0]["text"].strip()
            return text
    except Exception:
        pass

    # ── Rule-based fallback ───────────────────────────────────────────────────
    return _rule_based_conclusion(data, context)


def _n(val, fmt=".1f", fallback="N/A"):
    """Safely format a number; return fallback if None."""
    if val is None:
        return fallback
    try:
        return format(val, fmt)
    except Exception:
        return fallback


def _rule_based_conclusion(data, ctx):
    ticker  = ctx["ticker"]
    company = ctx["company"] or ticker

    # Verdict
    signals = []
    if ctx["pe_trailing"] and ctx["pe_trailing"] < 20:   signals.append(1)
    elif ctx["pe_trailing"] and ctx["pe_trailing"] > 35: signals.append(-1)
    ms = ctx["dcf_margin_safety_pct"]
    if ms is not None:
        if ms > 15:   signals.append(1)
        elif ms < -20: signals.append(-1)
    pf = ctx["piotroski_f"]
    if pf is not None:
        if pf >= 7:  signals.append(1)
        elif pf <= 3: signals.append(-1)
    az = ctx["altman_z"]
    if az is not None:
        if az > 3:   signals.append(1)
        elif az < 1.8: signals.append(-1)

    net = sum(signals)
    verdict = "broadly bullish" if net >= 2 else "broadly bearish" if net <= -2 else "broadly neutral"

    # Valuation note
    val_note = ""
    if ms is not None:
        if ms > 20:
            val_note = f"The DCF model indicates the stock may be undervalued by approximately {_n(ms, '.0f')}% relative to intrinsic value."
        elif ms < -20:
            val_note = f"The DCF model suggests the stock trades at a {_n(abs(ms), '.0f')}% premium to intrinsic value, raising concerns about downside risk."
        else:
            val_note = "The DCF model places the stock in roughly fair-value territory."
    else:
        val_note = "A DCF intrinsic value could not be calculated due to insufficient free cash flow data."

    # Sentiment note
    sent_overall = ctx.get("sentiment_overall") or "Neutral"
    sent_pos     = ctx.get("sentiment_positive_pct") or 0
    corr = "corroborates" if "ositive" in sent_overall else "conflicts with"
    sent_note = (f"News sentiment is {sent_overall.lower()} with {_n(sent_pos, '.0f')}% positive headlines, "
                 f"which broadly {corr} the quantitative picture.")

    # Health note
    health_note = ""
    if az is not None:
        if az > 2.99:
            health_note = f"The Altman Z-Score of {_n(az, '.2f')} places the company in the safe zone, indicating low bankruptcy risk."
        elif az < 1.81:
            health_note = f"The Altman Z-Score of {_n(az, '.2f')} raises distress flags and warrants close monitoring."
        else:
            health_note = f"The Altman Z-Score of {_n(az, '.2f')} sits in the grey zone, suggesting moderate financial caution."

    # Return / Sharpe
    ret1y  = ctx.get("return_1y_pct")
    sharpe = ctx.get("sharpe_ratio")
    if ret1y is not None and sharpe is not None:
        perf_note = (f"The one-year return of {_n(ret1y, '+.1f')}% with a Sharpe ratio of {_n(sharpe, '.2f')} indicates "
                     f"{'risk-adjusted outperformance' if sharpe > 1 else 'below-average risk-adjusted returns'}.")
    elif ret1y is not None:
        perf_note = f"The stock delivered a one-year return of {_n(ret1y, '+.1f')}%."
    else:
        perf_note = "Insufficient price history to compute a full-year return."

    rev_growth  = ctx.get("revenue_growth_pct") or 0
    net_margin  = ctx.get("net_margin_pct")      or 0
    prof_word   = "healthy" if net_margin > 10 else "modest"
    rec         = ctx.get("analyst_recommendation") or "N/A"

    return (
        f"Based on the comprehensive analysis, the overall picture for {company} ({ticker}) is {verdict}. "
        f"{val_note} "
        f"The Piotroski F-Score of {pf if pf is not None else 'N/A'} out of 9 reflects the breadth of financial health signals. "
        f"{health_note} "
        f"Revenue growth of {_n(rev_growth, '+.1f')}% and net margins of {_n(net_margin, '.1f')}% "
        f"paint a picture of {prof_word} profitability. "
        f"{perf_note} "
        f"{sent_note} "
        f"Investors should weigh the analyst consensus of {rec} "
        f"against the full range of fundamentals outlined in this report before making any investment decision."
    )
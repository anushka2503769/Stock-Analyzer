"""
analyzer.py — Fetches all financial data and computes every metric.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings, requests, feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────
#  HELPER UTILITIES
# ─────────────────────────────────────────────

def safe(val, default=None):
    """Return val unless it's NaN / None."""
    try:
        if val is None:
            return default
        if isinstance(val, float) and np.isnan(val):
            return default
        return val
    except Exception:
        return default


def pct_change(new, old):
    if old and old != 0:
        return (new - old) / abs(old) * 100
    return None


# ─────────────────────────────────────────────
#  MAIN ANALYSER CLASS
# ─────────────────────────────────────────────

class StockAnalyzer:
    def __init__(self, ticker: str):
        self.ticker = self._resolve_ticker(ticker.upper())
        self.yf_obj = yf.Ticker(self.ticker)

    @staticmethod
    def _resolve_ticker(ticker: str) -> str:
        """
        Auto-append exchange suffix for non-US markets when the user omits it.
          Indian NSE  -> .NS   (HDFCBANK -> HDFCBANK.NS)
          Indian BSE  -> .BO
          Hong Kong   -> .HK   (9988 -> 9988.HK)
          London      -> .L
          Toronto     -> .TO   Frankfurt -> .DE  Paris -> .PA  Sydney -> .AX
        Tickers already containing "." are returned unchanged (e.g. BRK.B, 9988.HK).
        """
        if "." in ticker:
            return ticker

        # Known Indian NSE blue-chips - resolve immediately without a network call
        INDIAN_NSE = {
            "HDFCBANK","RELIANCE","TCS","INFY","WIPRO","ICICIBANK","SBIN",
            "BAJFINANCE","HINDUNILVR","KOTAKBANK","AXISBANK","MARUTI","TITAN",
            "NESTLEIND","ULTRACEMCO","ADANIENT","ADANIPORTS","SUNPHARMA","ONGC",
            "NTPC","POWERGRID","TECHM","HCLTECH","LTIM","LT","ITC","BHARTIARTL",
            "ASIANPAINT","DIVISLAB","DRREDDY","CIPLA","EICHERMOT","BAJAJFINSV",
            "BPCL","COALINDIA","HEROMOTOCO","HINDALCO","INDUSINDBK","JSWSTEEL",
            "M&M","SBILIFE","TATAMOTORS","TATACONSUM","TATASTEEL","UPL","VEDL",
            "GRASIM","ZOMATO","PAYTM","NYKAA","POLICYBZR","IRCTC","DMART","HAL",
            "BEL","RECLTD","PFC","IRFC","NHPC","SJVN","CANBK","BANKBARODA",
            "PNB","FEDERALBNK","IDFCFIRSTB","RBLBANK","BANDHANBNK","AUBANK",
        }
        if ticker in INDIAN_NSE:
            return ticker + ".NS"

        # Pure-digit tickers are almost certainly Hong Kong
        if ticker.isdigit():
            return ticker + ".HK"

        # For everything else: try as-is first (US market), then .NS fallback
        try:
            fi = yf.Ticker(ticker).fast_info
            price = getattr(fi, "last_price", None)
            if price is not None and not (isinstance(price, float) and np.isnan(price)):
                return ticker
        except Exception:
            pass

        # Try NSE suffix
        try:
            fi = yf.Ticker(ticker + ".NS").fast_info
            price = getattr(fi, "last_price", None)
            if price is not None and not (isinstance(price, float) and np.isnan(price)):
                print(f"  i  Auto-resolved {ticker} -> {ticker}.NS (NSE India)")
                return ticker + ".NS"
        except Exception:
            pass

        return ticker   # return as-is and let yfinance surface the error

    # ── master runner ──────────────────────────
    def run_full_analysis(self):
        print(f"  [1/7] Fetching company info...")
        info = self._get_info()
        if not info:
            return None

        print(f"  [2/7] Fetching price history & technicals...")
        price_data = self._get_price_data()

        print(f"  [3/7] Computing valuation metrics...")
        valuation = self._get_valuation(info)

        print(f"  [4/7] Computing financial health metrics...")
        health = self._get_financial_health(info)

        print(f"  [5/7] Computing growth & profitability metrics...")
        growth = self._get_growth_profitability(info)

        print(f"  [6/7] Fetching news sentiment...")
        sentiment = self._get_news_sentiment()

        print(f"  [7/7] Building DCF & analyst estimates...")
        dcf = self._get_dcf_and_estimates(info)

        return {
            "ticker": self.ticker,
            "info": info,
            "price_data": price_data,
            "valuation": valuation,
            "health": health,
            "growth": growth,
            "sentiment": sentiment,
            "dcf": dcf,
            "generated_at": datetime.now().strftime("%d %B %Y, %H:%M"),
        }

    # ── 1. Company info ────────────────────────
    def _get_info(self):
        try:
            info = self.yf_obj.info
            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                return None
            return info
        except Exception:
            return None

    # ── 2. Price data & technicals ─────────────
    def _get_price_data(self):
        hist_5y  = self.yf_obj.history(period="5y",  interval="1wk")
        hist_1y  = self.yf_obj.history(period="1y",  interval="1d")
        hist_6m  = self.yf_obj.history(period="6mo", interval="1d")

        result = {
            "hist_5y": hist_5y,
            "hist_1y": hist_1y,
            "hist_6m": hist_6m,
        }

        if len(hist_1y) < 20:
            return result

        close = hist_1y["Close"]

        # Moving averages
        result["ma50"]  = close.rolling(50).mean()
        result["ma200"] = close.rolling(200).mean()
        result["ma20"]  = close.rolling(20).mean()

        # Bollinger Bands
        std20 = close.rolling(20).std()
        result["bb_upper"] = result["ma20"] + 2 * std20
        result["bb_lower"] = result["ma20"] - 2 * std20

        # RSI (14)
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        result["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        result["macd"]        = ema12 - ema26
        result["macd_signal"] = result["macd"].ewm(span=9, adjust=False).mean()
        result["macd_hist"]   = result["macd"] - result["macd_signal"]

        # Volume profile
        result["vol_ma20"] = hist_1y["Volume"].rolling(20).mean()

        # 52-week high/low
        result["52w_high"] = close.max()
        result["52w_low"]  = close.min()
        result["current"]  = close.iloc[-1]
        result["pct_from_52w_high"] = (result["current"] / result["52w_high"] - 1) * 100
        result["pct_from_52w_low"]  = (result["current"] / result["52w_low"]  - 1) * 100

        # ATR (14-day)
        h = hist_1y["High"]; l = hist_1y["Low"]; c = hist_1y["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        result["atr"] = tr.rolling(14).mean().iloc[-1]

        # Beta-adjusted volatility
        result["annualised_vol"] = close.pct_change().std() * np.sqrt(252) * 100

        # Returns
        if len(close) >= 252:
            result["return_1y"] = (close.iloc[-1] / close.iloc[-252] - 1) * 100
        if len(close) >= 126:
            result["return_6m"] = (close.iloc[-1] / close.iloc[-126] - 1) * 100
        if len(close) >= 21:
            result["return_1m"] = (close.iloc[-1] / close.iloc[-21] - 1) * 100
        if len(close) >= 5:
            result["return_1w"] = (close.iloc[-1] / close.iloc[-5]  - 1) * 100

        # Sharpe (risk-free 5%)
        daily_ret = close.pct_change().dropna()
        rf_daily  = 0.05 / 252
        result["sharpe"] = (daily_ret.mean() - rf_daily) / daily_ret.std() * np.sqrt(252)

        # Drawdown
        roll_max = close.cummax()
        drawdown = (close - roll_max) / roll_max * 100
        result["max_drawdown"] = drawdown.min()

        return result

    # ── 3. Valuation ───────────────────────────
    def _get_valuation(self, info):
        v = {}
        fields = [
            "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
            "enterpriseToEbitda", "enterpriseToRevenue", "trailingEps", "forwardEps",
            "pegRatio", "bookValue", "enterpriseValue", "marketCap",
            "dividendYield", "payoutRatio", "fiveYearAvgDividendYield",
            "trailingAnnualDividendRate",
        ]
        for f in fields:
            v[f] = safe(info.get(f))

        # EV/FCF
        fcf = safe(info.get("freeCashflow"))
        ev  = safe(info.get("enterpriseValue"))
        if fcf and ev and fcf > 0:
            v["ev_fcf"] = ev / fcf
        else:
            v["ev_fcf"] = None

        # Price/FCF
        price = safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        shares = safe(info.get("sharesOutstanding"))
        if fcf and shares and shares > 0 and price:
            v["price_fcf"] = price / (fcf / shares)
        else:
            v["price_fcf"] = None

        # Graham Number
        eps = safe(info.get("trailingEps"))
        bvps = safe(info.get("bookValue"))
        if eps and bvps and eps > 0 and bvps > 0:
            v["graham_number"] = np.sqrt(22.5 * eps * bvps)
        else:
            v["graham_number"] = None

        v["current_price"] = price
        return v

    # ── 4. Financial health ────────────────────
    def _get_financial_health(self, info):
        h = {}
        fields = [
            "currentRatio", "quickRatio", "totalDebt", "totalCash",
            "debtToEquity", "returnOnAssets", "returnOnEquity",
            "totalRevenue", "grossProfits", "ebitda", "operatingCashflow",
            "freeCashflow", "netIncomeToCommon", "totalAssets",
            "totalStockholderEquity",
        ]
        for f in fields:
            h[f] = safe(info.get(f))

        # Debt/EBITDA
        debt   = safe(info.get("totalDebt"))
        ebitda = safe(info.get("ebitda"))
        if debt and ebitda and ebitda > 0:
            h["debt_ebitda"] = debt / ebitda
        else:
            h["debt_ebitda"] = None

        # Net debt
        cash = safe(info.get("totalCash"))
        if debt is not None and cash is not None:
            h["net_debt"] = debt - cash
        else:
            h["net_debt"] = None

        # Interest coverage (EBIT / Interest Expense) — approximate via financials
        try:
            fin = self.yf_obj.financials
            if fin is not None and not fin.empty:
                interest_rows = [r for r in fin.index if "interest" in r.lower() and "expense" in r.lower()]
                ebit_rows     = [r for r in fin.index if "ebit" == r.lower() or r.lower() == "operating income"]
                if interest_rows and ebit_rows:
                    interest = abs(fin.loc[interest_rows[0]].iloc[0])
                    ebit     = fin.loc[ebit_rows[0]].iloc[0]
                    if interest and interest != 0:
                        h["interest_coverage"] = ebit / interest
        except Exception:
            pass

        # Altman Z-Score (public manufacturing approximation)
        try:
            bs  = self.yf_obj.balance_sheet
            fin = self.yf_obj.financials
            if bs is not None and fin is not None and not bs.empty and not fin.empty:
                ta_key = [k for k in bs.index if "total assets" in k.lower()]
                cl_key = [k for k in bs.index if "current liabilities" in k.lower()]
                ca_key = [k for k in bs.index if "current assets" in k.lower()]
                re_key = [k for k in bs.index if "retained" in k.lower()]
                eq_key = [k for k in bs.index if "stockholder" in k.lower() and "equity" in k.lower()]
                rev_key = [k for k in fin.index if "total revenue" in k.lower()]
                ebit_key = [k for k in fin.index if k.lower() in ["ebit", "operating income"]]

                if all([ta_key, cl_key, ca_key, re_key, eq_key, rev_key]):
                    ta_ = bs.loc[ta_key[0]].iloc[0]
                    cl_ = bs.loc[cl_key[0]].iloc[0]
                    ca_ = bs.loc[ca_key[0]].iloc[0]
                    re_ = bs.loc[re_key[0]].iloc[0]
                    eq_ = bs.loc[eq_key[0]].iloc[0]
                    rev_ = fin.loc[rev_key[0]].iloc[0]
                    debt_ = safe(info.get("totalDebt")) or 0
                    mkt_  = safe(info.get("marketCap")) or 0

                    if ta_ and ta_ != 0:
                        wc  = (ca_ - cl_) / ta_
                        re_ratio  = re_ / ta_
                        ebit_ratio = (fin.loc[ebit_key[0]].iloc[0] / ta_) if ebit_key else 0
                        eq_debt = (mkt_ / debt_) if debt_ != 0 else 0
                        rev_ratio = rev_ / ta_

                        z = 1.2*wc + 1.4*re_ratio + 3.3*ebit_ratio + 0.6*eq_debt + rev_ratio
                        h["altman_z"] = round(z, 2)
        except Exception:
            pass

        # Piotroski F-Score (9-point)
        try:
            h["piotroski"] = self._calc_piotroski(info)
        except Exception:
            pass

        return h

    def _calc_piotroski(self, info):
        score = 0
        roa = safe(info.get("returnOnAssets"))
        ocf = safe(info.get("operatingCashflow"))
        if roa and roa > 0: score += 1
        if ocf and ocf > 0: score += 1
        # Leverage (debt ratio declining) — single-period proxy
        de = safe(info.get("debtToEquity"))
        if de and de < 100: score += 1
        cr = safe(info.get("currentRatio"))
        if cr and cr > 1: score += 1
        # Gross margin proxy
        gp = safe(info.get("grossProfits"))
        rev = safe(info.get("totalRevenue"))
        if gp and rev and rev > 0 and (gp/rev) > 0.2: score += 1
        roe = safe(info.get("returnOnEquity"))
        if roe and roe > 0: score += 1
        if roa and ocf and safe(info.get("totalAssets")):
            ta = info["totalAssets"]
            if ta and ocf / ta > roa: score += 1
        eps = safe(info.get("trailingEps"))
        if eps and eps > 0: score += 1
        return score

    # ── 5. Growth & profitability ──────────────
    def _get_growth_profitability(self, info):
        g = {}
        fields = [
            "revenueGrowth", "earningsGrowth", "revenuePerShare",
            "grossMargins", "operatingMargins", "profitMargins",
            "ebitdaMargins", "returnOnEquity", "returnOnAssets",
        ]
        for f in fields:
            g[f] = safe(info.get(f))

        # Historical revenue growth from financials
        try:
            fin = self.yf_obj.financials
            if fin is not None and not fin.empty:
                rev_row = [r for r in fin.index if "total revenue" in r.lower()]
                if rev_row:
                    revs = fin.loc[rev_row[0]].dropna()
                    if len(revs) >= 2:
                        g["revenue_yoy_1"] = pct_change(revs.iloc[0], revs.iloc[1])
                    if len(revs) >= 3:
                        g["revenue_yoy_2"] = pct_change(revs.iloc[1], revs.iloc[2])
                    if len(revs) >= 4:
                        g["revenue_cagr_3y"] = (revs.iloc[0] / revs.iloc[3]) ** (1/3) * 100 - 100
                    g["revenue_history"] = revs
        except Exception:
            pass

        # EPS history
        try:
            fin = self.yf_obj.financials
            if fin is not None and not fin.empty:
                ni_row = [r for r in fin.index if "net income" in r.lower()]
                if ni_row:
                    nis = fin.loc[ni_row[0]].dropna()
                    g["net_income_history"] = nis
        except Exception:
            pass

        # Analyst estimates
        try:
            est = self.yf_obj.earnings_estimate
            if est is not None:
                g["analyst_eps_estimate"] = est
        except Exception:
            pass

        g["earningsQuarterlyGrowth"] = safe(info.get("earningsQuarterlyGrowth"))
        return g

    # ── 6. News sentiment ──────────────────────
    def _get_news_sentiment(self):
        sia = SentimentIntensityAnalyzer()
        articles = []

        # Yahoo Finance RSS
        rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={self.ticker}&region=US&lang=en-US"
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:15]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                text    = f"{title}. {summary}"
                scores  = sia.polarity_scores(text)
                articles.append({
                    "title": title,
                    "source": "Yahoo Finance",
                    "published": entry.get("published", ""),
                    "compound": scores["compound"],
                    "pos": scores["pos"],
                    "neg": scores["neg"],
                    "neu": scores["neu"],
                    "label": "Positive" if scores["compound"] >= 0.05
                             else "Negative" if scores["compound"] <= -0.05
                             else "Neutral",
                })
        except Exception:
            pass

        # Also try yfinance news
        try:
            yn = self.yf_obj.news or []
            for item in yn[:10]:
                title = item.get("title", "")
                if not title:
                    continue
                # skip duplicates
                if any(a["title"] == title for a in articles):
                    continue
                scores = sia.polarity_scores(title)
                articles.append({
                    "title": title,
                    "source": item.get("publisher", "Unknown"),
                    "published": datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime("%Y-%m-%d") if item.get("providerPublishTime") else "",
                    "compound": scores["compound"],
                    "pos": scores["pos"],
                    "neg": scores["neg"],
                    "neu": scores["neu"],
                    "label": "Positive" if scores["compound"] >= 0.05
                             else "Negative" if scores["compound"] <= -0.05
                             else "Neutral",
                })
        except Exception:
            pass

        if not articles:
            return {"articles": [], "avg_compound": 0, "overall": "Neutral",
                    "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0, "accuracy_note": "No news found."}

        avg = np.mean([a["compound"] for a in articles])
        pos_pct = sum(1 for a in articles if a["label"] == "Positive") / len(articles) * 100
        neg_pct = sum(1 for a in articles if a["label"] == "Negative") / len(articles) * 100
        neu_pct = sum(1 for a in articles if a["label"] == "Neutral")  / len(articles) * 100

        overall = "Strongly Positive" if avg >= 0.3 \
             else "Positive"          if avg >= 0.05 \
             else "Negative"          if avg <= -0.05 \
             else "Strongly Negative" if avg <= -0.3 \
             else "Neutral"

        # Accuracy commentary
        if abs(avg) < 0.1:
            accuracy_note = "Sentiment signals are mixed with low conviction. Headlines alone carry limited predictive power in this range."
        elif abs(avg) >= 0.3:
            accuracy_note = "Strong sentiment detected. Research shows extreme sentiment can precede short-term price moves, but also reflects recency bias — treat with caution."
        else:
            accuracy_note = "Moderate sentiment detected. VADER headline analysis captures tone well, though it cannot account for sarcasm or complex financial language."

        return {
            "articles": articles[:20],
            "avg_compound": avg,
            "overall": overall,
            "positive_pct": pos_pct,
            "negative_pct": neg_pct,
            "neutral_pct": neu_pct,
            "accuracy_note": accuracy_note,
        }

    # ── 7. DCF & analyst targets ───────────────
    def _get_dcf_and_estimates(self, info):
        dcf = {}

        # Analyst price target
        dcf["target_mean"]   = safe(info.get("targetMeanPrice"))
        dcf["target_high"]   = safe(info.get("targetHighPrice"))
        dcf["target_low"]    = safe(info.get("targetLowPrice"))
        dcf["target_median"] = safe(info.get("targetMedianPrice"))
        dcf["analyst_count"] = safe(info.get("numberOfAnalystOpinions"))
        dcf["recommendation"] = safe(info.get("recommendationKey", "n/a"))

        current = safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        if current and dcf["target_mean"]:
            dcf["upside_mean"] = (dcf["target_mean"] / current - 1) * 100

        # Simple DCF: FCF-based
        fcf = safe(info.get("freeCashflow"))
        shares = safe(info.get("sharesOutstanding"))
        if fcf and shares and shares > 0 and current:
            g1 = safe(info.get("revenueGrowth")) or 0.05   # near-term growth
            g1 = min(max(g1, -0.1), 0.35)                  # cap at 35%
            g2 = 0.03                                       # terminal growth
            wacc = 0.09                                     # discount rate

            fcf_per_share = fcf / shares
            pv = 0
            cf = fcf_per_share
            for yr in range(1, 6):
                cf *= (1 + g1)
                pv += cf / (1 + wacc) ** yr
            # Terminal value
            tv = (cf * (1 + g2)) / (wacc - g2)
            pv += tv / (1 + wacc) ** 5

            dcf["dcf_intrinsic"]     = round(pv, 2)
            dcf["dcf_margin_safety"] = round((pv / current - 1) * 100, 1) if current else None
            dcf["dcf_g1"]  = g1
            dcf["dcf_g2"]  = g2
            dcf["dcf_wacc"] = wacc

        return dcf
#!/usr/bin/env python3
"""
Stock Fundamental Analysis Report Generator
Run: python main.py
"""

import sys
import os
from analyzer import StockAnalyzer
from report_generator import ReportGenerator

def main():
    print("\n" + "="*60)
    print("   📊  STOCK FUNDAMENTAL ANALYSIS REPORT GENERATOR")
    print("="*60)
    print("\nEnter stock ticker(s) separated by commas.")
    print("Examples: AAPL  |  AAPL, MSFT, GOOGL  |  TSLA, NVDA\n")

    raw = input("Tickers: ").strip()
    if not raw:
        print("No tickers entered. Exiting.")
        sys.exit(0)

    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    print(f"\n✅ Analysing: {', '.join(tickers)}\n")

    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)

    for ticker in tickers:
        print(f"\n{'─'*50}")
        print(f"  Processing {ticker}...")
        print(f"{'─'*50}")
        try:
            analyzer = StockAnalyzer(ticker)
            data = analyzer.run_full_analysis()
            if data is None:
                print(f"  ⚠️  Could not fetch data for {ticker}. Skipping.")
                continue
            gen = ReportGenerator(data, output_dir)
            path = gen.build()
            print(f"  ✅ Report saved: {path}")
        except Exception as e:
            print(f"  ❌ Error processing {ticker}: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  All reports saved to ./{output_dir}/")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

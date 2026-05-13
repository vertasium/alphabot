"""
AlphaBot v4.0 — Intraday & F&O Engine
Generates live intraday trade recommendations and simulated F&O calls
using 5m/15m timeframe momentum, VWAP, and Screener fundamentals.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("alphabot.intraday")

# F&O Approved List (subset for faster intraday scanning)
FO_SYMBOLS = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", 
    "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "TATAMOTORS.NS", "M&M.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "HCLTECH.NS"
]

class IntradayEngine:
    def __init__(self, data_engine, screener_engine):
        self.data_engine = data_engine
        self.screener = screener_engine
        self.intraday_calls = []
        self.last_update = None
        
    async def analyze_intraday(self):
        """Run intraday scan on F&O symbols"""
        try:
            calls = []
            
            import yfinance as yf
            # 1. Analyze Nifty & BankNifty first for market trend
            nifty_df = yf.download("^NSEI", period="5d", interval="5m", progress=False)
            bnifty_df = yf.download("^NSEBANK", period="5d", interval="5m", progress=False)
            
            nifty_trend = self._get_short_term_trend(nifty_df) if nifty_df is not None else 0
            bnifty_trend = self._get_short_term_trend(bnifty_df) if bnifty_df is not None else 0
            
            market_dir = "BULLISH" if nifty_trend > 0 else "BEARISH" if nifty_trend < 0 else "SIDEWAYS"
            
            # 2. Scan F&O stocks
            for symbol in FO_SYMBOLS:
                df = yf.download(symbol, period="5d", interval="5m", progress=False)
                if df is None or len(df) < 10:
                    continue
                    
                # Calculate VWAP
                df['typical'] = (df['High'] + df['Low'] + df['Close']) / 3
                df['vol_typ'] = df['typical'] * df['Volume']
                vwap = df['vol_typ'].sum() / (df['Volume'].sum() + 1e-9)
                
                # Get current stats
                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                avg_vol = df['Volume'].rolling(10).mean().iloc[-1]
                vol_spike = df['Volume'].iloc[-1] > (avg_vol * 1.05)  # Extremely relaxed for testing
                
                # Simple Intraday Momentum Setup
                setup = None
                call_type = None
                reason = ""
                
                # Distance to VWAP
                vwap_dist = (current_price - vwap) / vwap
                
                # VWAP Breakout
                if current_price > vwap and prev_price <= vwap:
                    setup = "LONG"
                    call_type = "BUY CALL (CE)"
                    reason = "VWAP Breakout"
                # VWAP Breakdown
                elif current_price < vwap and prev_price >= vwap:
                    setup = "SHORT"
                    call_type = "BUY PUT (PE)"
                    reason = "VWAP Breakdown"
                    
                # Trend continuation / Momentum
                elif vwap_dist > 0.001 and df['Close'].iloc[-1] > df['Close'].iloc[-2]:
                    setup = "LONG"
                    call_type = "BUY CALL (CE)"
                    reason = "Bullish Momentum above VWAP"
                elif vwap_dist < -0.001 and df['Close'].iloc[-1] < df['Close'].iloc[-2]:
                    setup = "SHORT"
                    call_type = "BUY PUT (PE)"
                    reason = "Bearish Weakness below VWAP"
                    
                # Watch (Near VWAP) or Fallback
                else:
                    setup = "WATCH"
                    call_type = "PREPARE"
                    reason = f"Monitoring near VWAP ({vwap_dist*100:.2f}%)"
                    
                if setup:
                    atr = df['High'].iloc[-5:].max() - df['Low'].iloc[-5:].min()
                    # Ensure ATR is not 0
                    if atr == 0: atr = current_price * 0.005
                    
                    sl = current_price - atr if setup in ["LONG", "WATCH"] else current_price + atr
                    target = current_price + (atr * 2) if setup in ["LONG", "WATCH"] else current_price - (atr * 2)
                    
                    # Try to fetch screener score
                    fund_data = self.screener.cache.get(symbol.replace('.NS',''), {})
                    fund_score = fund_data.get('fundamental_score', 50)
                    
                    # Boost confidence
                    confidence = 60
                    if vol_spike: confidence += 10
                    if setup == "LONG" and fund_score > 60: confidence += 15
                    if setup == "SHORT" and fund_score < 40: confidence += 15
                    if setup == "WATCH": confidence = 50
                    
                    calls.append({
                        "symbol": symbol.replace('.NS', ''),
                        "time": datetime.utcnow().strftime("%H:%M"),
                        "setup": setup,
                        "type": "F&O Intraday",
                        "action": call_type,
                        "entry": round(current_price, 2),
                        "stop_loss": round(sl, 2),
                        "target": round(target, 2),
                        "confidence": min(95, confidence),
                        "reason": reason,
                        "vwap": round(vwap, 2),
                        "market_context": market_dir
                    })
            
            # Sort by confidence
            calls.sort(key=lambda x: x['confidence'], reverse=True)
            self.intraday_calls = calls[:10]  # Top 10 calls
            self.last_update = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Intraday analysis error: {e}")

    def _get_short_term_trend(self, df: pd.DataFrame) -> int:
        if len(df) < 5: return 0
        recent = df['Close'].iloc[-5:]
        if recent.iloc[-1] > recent.iloc[0]: return 1
        elif recent.iloc[-1] < recent.iloc[0]: return -1
        return 0

    def get_calls(self):
        return self.intraday_calls

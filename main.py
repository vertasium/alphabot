"""
ALPHABOT v4.0 -- AI TRADING BOT (NSE/BSE India)
49 Strategies - 8 AI Agents - 10 Clusters - 6 Regimes
Prediction Engine + News Intelligence + Live NSE/BSE Data
"""
import asyncio, logging, sys, os, time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import DATA, TRADING, RISK, HOST, PORT
from core.data_ingestion import DataIngestionEngine
from core.feature_engine import FeatureEngine
from core.regime_detector import RegimeDetector
from core.news_engine import NewsEngine
from core.prediction_engine import PredictionEngine
from core.screener_engine import ScreenerEngine
from core.intraday_engine import IntradayEngine
from core.learning_engine import LearningEngine
from agents.all_agents import AgentCoordinator
from strategies.all_strategies import run_all_strategies
from signal_fusion.confirmation import confirm_signals
from risk.risk_manager import RiskManager
from execution.paper_trader import PaperTrader
from api.routes import router, set_engine, ws_manager, ws_endpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("alphabot")


class AlphaBotEngine:
    """Core trading engine — NSE/BSE with prediction & news intelligence"""

    def __init__(self):
        self.data_engine       = DataIngestionEngine(DATA.universe_symbols, DATA.lookback_days)
        self.feature_engine    = FeatureEngine()
        self.regime_detector   = RegimeDetector()
        self.news_engine       = NewsEngine()
        self.prediction_engine = PredictionEngine(news_engine=self.news_engine)
        self.screener_engine   = ScreenerEngine()
        self.intraday_engine   = IntradayEngine(self.data_engine, self.screener_engine)
        self.learning_engine   = LearningEngine(self.data_engine)
        self.agent_coordinator = AgentCoordinator()
        self.risk_manager      = RiskManager()
        self.paper_trader      = PaperTrader(TRADING.initial_capital)

        self.running = False
        self.cycle_count = 0
        self.current_regime = "initializing"
        self.regime_confidence = 0.0
        self.latest_signals: list = []
        self.latest_agent_predictions: dict = {}
        self.stock_rankings: list = []
        self.equity_curve: list = [TRADING.initial_capital]
        self.market_summary: dict = {}
        self.news_cycle = 0     # Track news refresh cycles
        self._initialized = False

    async def initialize(self):
        logger.info("=" * 65)
        logger.info("  ALPHABOT v4.0 -- NSE/BSE PREDICTION BOT (India)")
        logger.info("=" * 65)

        # Data first
        await self.data_engine.initialize()

        logger.info("  Fetching fundamental data...")
        await self.screener_engine.initialize()
        
        # Evaluate past predictions
        self.learning_engine.evaluate_past_predictions()
        
        # Pre-fetch fundamentals for FO_SYMBOLS
        from core.intraday_engine import FO_SYMBOLS
        async def fetch_all():
            await asyncio.gather(*[self.screener_engine.fetch_fundamentals(s) for s in FO_SYMBOLS])
        asyncio.create_task(fetch_all())

        # News in parallel
        logger.info("  Fetching market news...")
        await self.news_engine.initialize()

        self._initialized = True
        self.running = True

        nse = self.data_engine.get_nse_symbols()
        bse = self.data_engine.get_bse_symbols()
        india_vix = self.data_engine.get_india_vix()
        nifty = self.data_engine.get_nifty_price()

        logger.info(f"  NSE: {len(nse)} symbols | BSE: {len(bse)} symbols")
        logger.info(f"  Nifty 50: {nifty:,.2f} | India VIX: {india_vix:.2f}")
        logger.info(f"  News: {len(self.news_engine.news_cache)} articles loaded")
        logger.info(f"  Capital: Rs. {TRADING.initial_capital:,.0f}")
        logger.info(f"  Prediction Engine: ACTIVE")
        logger.info("=" * 65)

    async def run_cycle(self):
        if not self._initialized or not self.running:
            return

        self.cycle_count += 1
        cycle_start = time.time()

        try:
            # ── 1. Market Context ─────────────────────────
            india_vix  = self.data_engine.get_india_vix()
            nifty      = self.data_engine.get_nifty_price()
            nifty_ema  = self.data_engine.get_nifty_ema200()
            banknifty  = self.data_engine.get_banknifty_price()
            sensex     = self.data_engine.get_sensex_price()

            # Nifty features for regime
            nifty_features = {}
            nifty_df = self.data_engine.get_ohlcv("^NSEI", 60)
            if nifty_df is not None and len(nifty_df) >= 14:
                nifty_features = self.feature_engine.compute_features(nifty_df, "NIFTY50")

            market_data = {
                'vix': india_vix, 'spy_price': nifty,
                'spy_ema200': nifty_ema,
                'adx': nifty_features.get('adx_14', 20),
                'plus_di': nifty_features.get('plus_di', 0),
                'minus_di': nifty_features.get('minus_di', 0),
                'avg_correlation': 0.35, 'sector_breadth': 0.5,
                'nifty': nifty, 'banknifty': banknifty, 'india_vix': india_vix
            }

            # ── 2. Regime Detection ───────────────────────
            regime_result = self.regime_detector.detect(market_data)
            self.current_regime = regime_result.regime.value
            self.regime_confidence = regime_result.confidence
            self.paper_trader.portfolio.regime = self.current_regime
            self.paper_trader.portfolio.vix = india_vix

            self.market_summary = {
                'nifty50': round(nifty, 2),
                'nifty_change': round(nifty_features.get('returns_1d', 0) * 100, 2),
                'banknifty': round(banknifty, 2),
                'sensex': round(sensex, 2),
                'india_vix': round(india_vix, 2),
                'regime': self.current_regime,
                'adx': round(nifty_features.get('adx_14', 20), 1),
                'rsi': round(nifty_features.get('rsi_14', 50), 1),
                'news_sentiment': round(self.news_engine.market_sentiment, 3),
                'news_count': len(self.news_engine.news_cache)
            }

            # ── 3. News Refresh (every 3 cycles ~2.25 min) ──
            self.news_cycle += 1
            if self.news_cycle % 3 == 1 or self.news_engine.should_refresh():
                asyncio.create_task(self.news_engine.fetch_all_news())

            # ── 3.5 Intraday & F&O Scan ──
            if self.cycle_count % 2 == 0:
                asyncio.create_task(self.intraday_engine.analyze_intraday())

            # ── 4. Per-symbol Analysis ────────────────────
            symbols  = self.data_engine.get_available_symbols()
            all_signals   = []
            rankings      = []
            predictions   = []
            agent_preds_set = False

            for symbol in symbols[:70]:
                df = self.data_engine.get_ohlcv(symbol, DATA.feature_window)
                if df is None or len(df) < 20:
                    continue

                features = self.feature_engine.compute_features(df, symbol)
                if not features or features.get('price', 0) <= 0:
                    continue

                agent_result = self.agent_coordinator.predict_all(features, market_data)
                display = self.data_engine.get_display_name(symbol)

                rankings.append({
                    'symbol': display, 'full_symbol': symbol,
                    'exchange': self.data_engine.get_exchange(symbol),
                    'score': round(agent_result['composite_probability'] * 100, 1),
                    'action': agent_result['action'],
                    'confidence': round(agent_result['confidence'] * 100, 1),
                    'sector': self.data_engine.get_sector(symbol),
                    'price': round(features.get('price', 0), 2),
                    'returns_1d': round(features.get('returns_1d', 0) * 100, 2),
                    'rsi': round(features.get('rsi_14', 50), 1),
                    'adx': round(features.get('adx_14', 20), 1),
                    'macd_hist': round(features.get('macd_histogram', 0), 4),
                    'atr': round(features.get('atr_14', 0), 2)
                })

                if not agent_preds_set and agent_result['confidence'] > 0.3:
                    self.latest_agent_predictions = agent_result.get('predictions', {})
                    agent_preds_set = True

                # Run strategies
                signals = run_all_strategies(features, symbol, self.current_regime)
                all_signals.extend(signals)

                # ── Prediction ──────────────────────────
                pred = self.prediction_engine.predict_stock(
                    symbol, features, agent_result, signals, market_data, self.current_regime
                )
                if pred:
                    self.prediction_engine.predictions[symbol] = pred
                    predictions.append(pred)

            # ── 5. Market Outlook ─────────────────────────
            if nifty_features and predictions:
                self.prediction_engine.generate_market_outlook(
                    nifty_features, india_vix, self.current_regime,
                    self.news_engine.market_sentiment, predictions,
                    self.news_engine
                )

            # ── 6. Signal Fusion & Execution ─────────────
            confirmed = confirm_signals(all_signals, min_confirmations=2, min_confidence=0.58)
            self.latest_signals = confirmed[:20] + all_signals[:5]

            rankings.sort(key=lambda x: x['score'], reverse=True)
            self.stock_rankings = rankings

            breakers = self.risk_manager.check_circuit_breakers(self.paper_trader.portfolio)
            if breakers['trading_allowed']:
                for signal in confirmed[:5]:
                    v = self.risk_manager.validate_signal(signal, self.paper_trader.portfolio)
                    if v['valid']:
                        pos_val = self.risk_manager.size_position(signal, self.paper_trader.portfolio)
                        if pos_val > 0:
                            self.paper_trader.execute_signal(signal, pos_val)

            self.paper_trader.update_prices(self.data_engine.latest_prices)
            self.equity_curve.append(round(self.paper_trader.portfolio.equity, 2))

            # ── 7. WebSocket Broadcast ────────────────────
            cycle_time = (time.time() - cycle_start) * 1000
            p = self.paper_trader.portfolio

            # Top recommendations for broadcast
            top_recs = self.prediction_engine.get_top_recommendations(5)
            outlook_dict = self.prediction_engine.market_outlook.to_dict() if self.prediction_engine.market_outlook else {}

            await ws_manager.broadcast({
                'type': 'cycle_update',
                'cycle': self.cycle_count,
                'regime': self.current_regime,
                'regime_confidence': round(self.regime_confidence, 2),
                'vix': round(india_vix, 2),
                'market': self.market_summary,
                'portfolio': p.to_dict(),
                'positions': len(self.paper_trader.positions),
                'signals': len(all_signals),
                'confirmed': len(confirmed),
                'predictions': len(predictions),
                'cycle_time_ms': round(cycle_time, 1),
                'rankings': rankings[:8],
                'top_recommendations': top_recs,
                'outlook': outlook_dict,
                'intraday_calls': self.intraday_engine.get_calls(),
                'news_sentiment': round(self.news_engine.market_sentiment, 3),
                'news_count': len(self.news_engine.news_cache),
                'nse_count': len(self.data_engine.get_nse_symbols()),
                'bse_count': len(self.data_engine.get_bse_symbols()),
                'timestamp': datetime.utcnow().isoformat()
            })

            if self.cycle_count % 3 == 0:
                outlook = self.prediction_engine.market_outlook
                nifty_pred = f"Nifty → {outlook.nifty_direction}" if outlook else "..."
                
            # Save today's predictions for tomorrow's learning evaluation
            if predictions:
                today_str = datetime.now().strftime('%Y-%m-%d')
                self.learning_engine.log_daily_predictions(today_str, predictions)
                logger.info(
                    f"[C{self.cycle_count}] {self.current_regime.upper()} | "
                    f"VIX:{india_vix:.1f} | Nifty:{nifty:,.0f} | "
                    f"Equity:Rs.{p.equity:,.0f}({p.total_pnl_pct:+.2f}%) | "
                    f"Pos:{p.num_positions} | Sigs:{len(all_signals)} | "
                    f"Preds:{len(predictions)} | {nifty_pred} | {cycle_time:.0f}ms"
                )

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)


# ── FastAPI App ──────────────────────────────────────────────────
engine = AlphaBotEngine()

async def trading_loop():
    while True:
        try:
            await engine.run_cycle()
            await asyncio.sleep(45)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(15)

async def fast_ticker_loop():
    """Fetches high-frequency price updates for dashboard tickers (simulating live broker feed)"""
    import yfinance as yf
    import pandas as pd
    while True:
        try:
            if engine.running and engine._initialized:
                # Essential tickers + active positions
                symbols = ["^NSEI", "^NSEBANK", "^INDIAVIX", "^BSESN"]
                positions = engine.paper_trader.get_positions()
                if positions:
                    symbols.extend([p['symbol'] for p in positions])
                
                # Fetch only 1 day, 1 min interval, just the 'Close' column
                data = yf.download(list(set(symbols)), period="1d", interval="1m", progress=False, show_errors=False)
                
                if data is not None and not data.empty and 'Close' in data:
                    close_data = data['Close']
                    prices = {}
                    
                    if isinstance(close_data, pd.DataFrame):
                        for sym in symbols:
                            if sym in close_data.columns and not pd.isna(close_data[sym].iloc[-1]):
                                prices[sym] = round(float(close_data[sym].iloc[-1]), 2)
                    elif isinstance(close_data, pd.Series):
                        # Only 1 symbol downloaded
                        sym = symbols[0]
                        if not pd.isna(close_data.iloc[-1]):
                            prices[sym] = round(float(close_data.iloc[-1]), 2)

                    if prices:
                        await ws_manager.broadcast({
                            'type': 'fast_tick',
                            'prices': prices,
                            'timestamp': datetime.utcnow().isoformat()
                        })
        except Exception as e:
            pass # Suppress fast ticker errors to keep logs clean
        
        await asyncio.sleep(4)  # Update every 4 seconds (fastest safe limit for YF)

@asynccontextmanager
async def lifespan(app):
    await engine.initialize()
    task_main = asyncio.create_task(trading_loop())
    task_fast = asyncio.create_task(fast_ticker_loop())
    yield
    engine.running = False
    task_main.cancel()
    task_fast.cancel()

app = FastAPI(title="AlphaBot v4.0 NSE/BSE", version="4.0.0", lifespan=lifespan)
app.include_router(router)
set_engine(engine)

@app.websocket("/ws/live")
async def ws_ep(websocket: WebSocket):
    await ws_endpoint(websocket)

dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/static", StaticFiles(directory=dashboard_dir), name="static")

@app.get("/")
async def root():
    idx = os.path.join(dashboard_dir, "index.html")
    return FileResponse(idx) if os.path.exists(idx) else {"msg": "AlphaBot v4.0"}


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  ALPHABOT v4.0 -- NSE/BSE PREDICTION BOT")
    print("  49 Strategies | 8 AI Agents | News Intel | Tomorrow's Picks")
    print("  Dashboard: http://localhost:8888")
    print("=" * 65 + "\n")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")

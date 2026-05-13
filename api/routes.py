"""
AlphaBot v4.0 — FastAPI Routes & WebSocket (NSE/BSE India)
REST API endpoints with Indian market data.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import List, Dict
import json, asyncio, logging
from datetime import datetime

logger = logging.getLogger("alphabot.api")
router = APIRouter(prefix="/api/v4")

# Global reference to trading engine
_engine = None

def set_engine(engine):
    global _engine
    _engine = engine


@router.get("/status")
async def get_status():
    if not _engine: return {"status": "not_initialized"}
    nse = len(_engine.data_engine.get_nse_symbols()) if _engine._initialized else 0
    bse = len(_engine.data_engine.get_bse_symbols()) if _engine._initialized else 0
    return {
        "status": "running" if _engine.running else "stopped",
        "regime": _engine.current_regime,
        "cycle_count": _engine.cycle_count,
        "nse_symbols": nse,
        "bse_symbols": bse,
        "total_symbols": nse + bse,
        "uptime_seconds": _engine.cycle_count * 45,
        "market": _engine.market_summary
    }

@router.get("/market")
async def get_market():
    """Indian market overview"""
    if not _engine: return {}
    return {
        **_engine.market_summary,
        "nse_count": len(_engine.data_engine.get_nse_symbols()),
        "bse_count": len(_engine.data_engine.get_bse_symbols()),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/portfolio")
async def get_portfolio():
    if not _engine: return {}
    p = _engine.paper_trader.portfolio.to_dict()
    p['currency'] = 'INR'
    p['currency_symbol'] = 'Rs.'
    return p

@router.get("/positions")
async def get_positions():
    if not _engine: return []
    positions = _engine.paper_trader.get_positions()
    # Add display name (strip .NS/.BO)
    for p in positions:
        p['display'] = p['symbol'].replace('.NS', '').replace('.BO', '')
        p['exchange'] = 'NSE' if p['symbol'].endswith('.NS') else 'BSE'
    return positions

@router.get("/trades")
async def get_trades():
    if not _engine: return []
    trades = _engine.paper_trader.get_recent_trades(100)
    for t in trades:
        t['display'] = t['symbol'].replace('.NS', '').replace('.BO', '')
        t['exchange'] = 'NSE' if t['symbol'].endswith('.NS') else 'BSE'
    return trades

@router.get("/signals")
async def get_signals():
    if not _engine: return []
    return [{
        "symbol": s.symbol.replace('.NS', '').replace('.BO', ''),
        "full_symbol": s.symbol,
        "exchange": "NSE" if s.symbol.endswith('.NS') else "BSE",
        "direction": s.direction.value,
        "confidence": round(s.confidence, 3),
        "entry_price": round(s.entry_price, 2),
        "stop_loss": round(s.stop_loss, 2),
        "take_profit": round(s.take_profit, 2),
        "strategy_id": s.strategy_id,
        "cluster": s.cluster,
        "timestamp": s.timestamp
    } for s in _engine.latest_signals[-50:]]

@router.get("/agents")
async def get_agents():
    if not _engine: return {}
    return _engine.latest_agent_predictions

@router.get("/regime")
async def get_regime():
    if not _engine: return {}
    return {
        "regime": _engine.current_regime,
        "confidence": _engine.regime_confidence,
        "india_vix": _engine.paper_trader.portfolio.vix,
        "nifty50": _engine.market_summary.get('nifty50', 0),
        "banknifty": _engine.market_summary.get('banknifty', 0),
        "adx": _engine.market_summary.get('adx', 0),
        "rsi": _engine.market_summary.get('rsi', 50)
    }

@router.get("/ranking")
async def get_ranking():
    if not _engine: return []
    return _engine.stock_rankings[:30]

@router.get("/ranking/nse")
async def get_nse_ranking():
    if not _engine: return []
    return [r for r in _engine.stock_rankings if r.get('exchange') == 'NSE'][:20]

@router.get("/ranking/bse")
async def get_bse_ranking():
    if not _engine: return []
    return [r for r in _engine.stock_rankings if r.get('exchange') == 'BSE'][:20]

@router.get("/ranking/sector/{sector}")
async def get_sector_ranking(sector: str):
    if not _engine: return []
    return [r for r in _engine.stock_rankings
            if r.get('sector', '').lower() == sector.lower()]

@router.get("/sectors")
async def get_sectors():
    """Return all available sectors with their top stocks"""
    if not _engine: return {}
    sectors: Dict[str, list] = {}
    for r in _engine.stock_rankings:
        sec = r.get('sector', 'Unknown')
        if sec not in sectors:
            sectors[sec] = []
        if len(sectors[sec]) < 5:
            sectors[sec].append(r)
    return sectors

@router.get("/performance")
async def get_performance():
    if not _engine: return {}
    p = _engine.paper_trader.portfolio
    trades = _engine.paper_trader.trade_history
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]
    return {
        "total_return_pct": round(p.total_pnl_pct, 2),
        "total_pnl_inr": round(p.total_pnl, 2),
        "sharpe_ratio": round(p.sharpe_ratio, 2),
        "max_drawdown_pct": round(p.drawdown_pct * 100, 2),
        "win_rate": round(p.win_rate * 100, 1),
        "total_trades": p.total_trades,
        "winning_trades": p.winning_trades,
        "losing_trades": p.losing_trades,
        "avg_win_inr": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss_inr": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else 0,
        "equity_curve": _engine.equity_curve[-200:],
        "currency": "INR"
    }

@router.post("/emergency-stop")
async def emergency_stop():
    if not _engine: return {"error": "not initialized"}
    _engine.running = False
    prices = _engine.data_engine.latest_prices
    _engine.paper_trader.close_all(prices, "EMERGENCY_STOP")
    return {"status": "halted", "positions_closed": True, "timestamp": datetime.utcnow().isoformat()}

@router.post("/start")
async def start_trading():
    if not _engine: return {"error": "not initialized"}
    _engine.running = True
    return {"status": "started"}

@router.post("/stop")
async def stop_trading():
    if not _engine: return {"error": "not initialized"}
    _engine.running = False
    return {"status": "stopped"}


# ═══════════════════════════════════════════════════════════════
# PREDICTION & RECOMMENDATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/predictions")
async def get_predictions():
    """All next-day stock predictions"""
    if not _engine: return []
    return _engine.prediction_engine.get_all_predictions()

@router.get("/predictions/top")
async def get_top_predictions():
    """Top actionable recommendations (graded A+/A/B+)"""
    if not _engine: return []
    return _engine.prediction_engine.get_top_recommendations(15)

@router.get("/predictions/{symbol}")
async def get_stock_prediction(symbol: str):
    """Prediction for a specific stock (use RELIANCE, TCS, etc.)"""
    if not _engine: return {"error": "not initialized"}
    # Try with .NS then .BO suffix
    for suffix in ['.NS', '.BO', '']:
        key = symbol.upper() + suffix
        pred = _engine.prediction_engine.predictions.get(key)
        if pred:
            return pred.to_dict()
    return {"error": f"No prediction for {symbol}. Run a cycle first."}

@router.get("/outlook")
async def get_market_outlook():
    """Tomorrow's full market outlook (Nifty direction, sector rotation, top picks)"""
    if not _engine: return {}
    outlook = _engine.prediction_engine.market_outlook
    if not outlook:
        return {"status": "Generating... run a cycle first"}
    return outlook.to_dict()

@router.get("/recommendations")
async def get_recommendations():
    """Curated buy/sell recommendations with entry, SL, targets for tomorrow"""
    if not _engine: return []
    recs = _engine.prediction_engine.get_top_recommendations(20)
    # Enrich with news
    for rec in recs:
        sym = rec.get('symbol', '') + '.NS'
        news = _engine.news_engine.get_symbol_news(sym, 3)
        rec['related_news'] = [n['title'] for n in news]
    return recs

# ═══════════════════════════════════════════════════════════════
# NEWS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/news")
async def get_news():
    """Latest market news with sentiment"""
    if not _engine: return []
    return _engine.news_engine.get_latest_news(40)

@router.get("/news/high-impact")
async def get_high_impact_news():
    """High-impact news only"""
    if not _engine: return []
    return _engine.news_engine.get_high_impact_news(15)

@router.get("/news/sentiment")
async def get_news_sentiment():
    """Overall market news sentiment"""
    if not _engine: return {}
    ne = _engine.news_engine
    return {
        "market_sentiment_score": round(ne.market_sentiment, 3),
        "market_sentiment_label": "BULLISH" if ne.market_sentiment > 0.1 else "BEARISH" if ne.market_sentiment < -0.1 else "NEUTRAL",
        "total_articles": len(ne.news_cache),
        "high_impact": len([n for n in ne.news_cache if n.impact == 'HIGH']),
        "macro_news": len(ne.macro_news),
        "last_updated": ne.last_fetch.isoformat() if ne.last_fetch else None,
        "sources": list(set(n.source for n in ne.news_cache[:20]))
    }

@router.get("/news/{symbol}")
async def get_stock_news(symbol: str):
    """News affecting a specific stock"""
    if not _engine: return []
    sym_ns = symbol.upper() + '.NS'
    sym_bo = symbol.upper() + '.BO'
    news = _engine.news_engine.get_symbol_news(sym_ns, 10)
    if not news:
        news = _engine.news_engine.get_symbol_news(sym_bo, 10)
    return news

@router.get("/learning/stats")
async def get_learning_stats():
    """Get AI prediction accuracy and learning insights"""
    if not _engine or not hasattr(_engine, 'learning_engine'):
        return {"error": "not initialized"}
    return _engine.learning_engine.get_dashboard_data()

@router.post("/news/refresh")
async def refresh_news():
    """Manually trigger news refresh"""
    if not _engine: return {"error": "not initialized"}
    asyncio.create_task(_engine.news_engine.fetch_all_news())
    return {"status": "refresh_triggered", "timestamp": datetime.utcnow().isoformat()}

# ═══════════════════════════════════════════════════════════════
# DASHBOARD FAST SYNC
# ═══════════════════════════════════════════════════════════════
@router.get("/dashboard/sync")
async def get_dashboard_sync():
    """Returns the latest cycle data instantly for browser refreshes"""
    if not _engine or not _engine._initialized:
        return {"status": "initializing"}
        
    p = _engine.paper_trader.portfolio
    top_recs = _engine.prediction_engine.get_top_recommendations(5)
    outlook_dict = _engine.prediction_engine.market_outlook.to_dict() if getattr(_engine.prediction_engine, 'market_outlook', None) else {}
    
    return {
        'type': 'cycle_update',
        'cycle': getattr(_engine, 'cycle_count', 0),
        'regime': getattr(_engine, 'current_regime', 'UNKNOWN'),
        'portfolio': p.to_dict() if p else {},
        'market': getattr(_engine, 'market_summary', {}),
        'confirmed': len(getattr(_engine, 'latest_signals', [])),
        'predictions': len(_engine.prediction_engine.predictions) if _engine.prediction_engine else 0,
        'rankings': getattr(_engine, 'stock_rankings', [])[:8],
        'top_recommendations': top_recs,
        'outlook': outlook_dict,
        'intraday_calls': _engine.intraday_engine.get_calls() if getattr(_engine, 'intraday_engine', None) else [],
        'news_sentiment': round(_engine.news_engine.market_sentiment, 3) if getattr(_engine, 'news_engine', None) else 0,
        'news_count': len(_engine.news_engine.news_cache) if getattr(_engine, 'news_engine', None) else 0,
        'nse_count': len(_engine.data_engine.get_nse_symbols()) if getattr(_engine, 'data_engine', None) else 0,
        'bse_count': len(_engine.data_engine.get_bse_symbols()) if getattr(_engine, 'data_engine', None) else 0
    }

# ═══════════════════════════════════════════════════════════════
# INTRADAY & F&O ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/intraday")
async def get_intraday_calls():
    """Live intraday & F&O recommendations based on 5m VWAP"""
    if not _engine: return []
    return _engine.intraday_engine.get_calls()

@router.get("/screener/{symbol}")
async def get_screener_data(symbol: str):
    """Screener.in fundamentals for a stock"""
    if not _engine: return {}
    base_sym = symbol.replace('.NS', '').replace('.BO', '').upper()
    return _engine.screener_engine.cache.get(base_sym, {})


# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = ConnectionManager()

async def ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

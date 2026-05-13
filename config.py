"""
AlphaBot v4.0 Configuration
Central configuration for all subsystems.
Market: NSE + BSE (India) with INR capital
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class TradingConfig:
    """Core trading parameters"""
    initial_capital: float = 50_000_000.0  # INR 5 Crore
    max_position_pct: float = 0.05         # 5% max per position
    max_sector_pct: float = 0.25           # 25% max per sector
    cash_reserve_pct: float = 0.20         # 20% min cash
    kelly_fraction: float = 0.25           # Quarter Kelly
    target_volatility: float = 0.12        # 12% annualized (Indian mkt is more volatile)
    min_confidence: float = 0.58
    min_confirmations: int = 2
    confirmation_confidence: float = 0.60
    currency: str = "INR"
    currency_symbol: str = "Rs."

@dataclass
class RiskConfig:
    """Risk management parameters"""
    daily_loss_limit: float = 0.02        # -2% daily
    strategy_drawdown_limit: float = 0.05  # -5% per strategy
    india_vix_circuit_breaker: float = 30.0  # India VIX is typically 12-40
    correlation_circuit_breaker: float = 0.85
    var_confidence: float = 0.99
    var_simulations: int = 10000
    max_gross_exposure: float = 1.50
    max_net_exposure: float = 1.00
    stop_loss_atr_multiplier: float = 1.5
    take_profit_r_multiple: float = 2.0
    # SEBI compliance
    sebi_position_limit_pct: float = 0.10  # 10% of portfolio per stock

@dataclass
class RegimeConfig:
    """Regime detection thresholds for Indian market"""
    bull_vix_max: float = 18.0         # India VIX ranges 10-85
    bull_adx_min: float = 22.0
    bear_vix_min: float = 22.0
    bear_adx_min: float = 22.0
    crash_vix_threshold: float = 35.0  # India VIX crash threshold
    crash_correlation_threshold: float = 0.85
    low_vol_vix_max: float = 14.0
    high_vol_vix_min: float = 25.0
    range_adx_max: float = 20.0

@dataclass
class DataConfig:
    """NSE/BSE stock universe - yfinance uses .NS for NSE, .BO for BSE"""

    # ─── NSE Large Cap (Nifty 50) ───
    nse_largecap: List[str] = field(default_factory=lambda: [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
        "INFOSYS.NS", "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS",
        "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "ASIANPAINT.NS",
        "HCLTECH.NS", "WIPRO.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
        "TECHM.NS", "TITAN.NS", "ULTRATECH.NS", "BAJAJFINSV.NS", "SUNPHARMA.NS",
        "TATAMOTORS.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "DIVISLAB.NS",
        "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HEROMOTOCO.NS", "HINDALCO.NS",
        "JSWSTEEL.NS", "M&M.NS", "NESTLEIND.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
        "TATACONSUM.NS", "TATASTEEL.NS", "APOLLOHOSP.NS", "BPCL.NS", "BRITANNIA.NS",
        "CIPLA.NS", "HDFCLIFE.NS", "INDUSINDBK.NS", "TRENT.NS", "BAJAJ-AUTO.NS"
    ])

    # ─── NSE Mid Cap ───
    nse_midcap: List[str] = field(default_factory=lambda: [
        "PERSISTENT.NS", "COFORGE.NS", "LTIM.NS", "MPHASIS.NS", "OFSS.NS",
        "BANKBARODA.NS", "CANBK.NS", "PNB.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS",
        "PIDILITIND.NS", "BERGEPAINT.NS", "ASTRAL.NS", "APLAPOLLO.NS", "POLYCAB.NS",
        "HAVELLS.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "BLUEDART.NS", "CONCOR.NS",
        "GMRAIRPORT.NS", "IRCTC.NS", "DMART.NS", "ZOMATO.NS", "NYKAA.NS",
        "PAYTM.NS", "POLICYBZR.NS", "CARTRADE.NS", "DELHIVERY.NS", "EASEMYTRIP.NS",
        "LICI.NS", "HAL.NS", "BEL.NS", "BHEL.NS", "SAIL.NS",
        "VEDL.NS", "HINDCOPPER.NS", "NATIONALUM.NS", "MOIL.NS", "NMDC.NS",
        "GODREJCP.NS", "MARICO.NS", "DABUR.NS", "EMAMILTD.NS", "COLPAL.NS",
        "TORNTPHARM.NS", "LUPIN.NS", "BIOCON.NS", "GLENMARK.NS", "ALKEM.NS"
    ])

    # ─── NSE Small Cap (high-growth) ───
    nse_smallcap: List[str] = field(default_factory=lambda: [
        "IDFC.NS", "RBLBANK.NS", "UJJIVAN.NS", "EQUITAS.NS",
        "KAJARIACER.NS", "SUPREMEIND.NS", "CERA.NS",
        "DIXON.NS", "AMBER.NS", "KAYNES.NS",
        "TATAELXSI.NS", "KPITTECH.NS", "LTTS.NS",
        "NAUKRI.NS", "JUSTDIAL.NS", "INDIAMART.NS",
        "METROPOLIS.NS", "LALPATHLAB.NS", "VIJAYABANK.NS",
        "ABCAPITAL.NS", "CHOICEIN.NS", "MANAPPURAM.NS"
    ])

    # ─── NSE Sector ETFs & Indices ───
    nse_etfs: List[str] = field(default_factory=lambda: [
        "^NSEI",      # Nifty 50
        "^NSEBANK",   # Nifty Bank
        "^CNXIT",     # Nifty IT
        "^CNXAUTO",   # Nifty Auto
        "^CNXPHARMA", # Nifty Pharma
        "^CNXFMCG",   # Nifty FMCG
        "^INDIAVIX",  # India VIX
        "NIFTYBEES.NS", "BANKBEES.NS", "ICICINIFTY.NS",
        "GOLDBEES.NS", "LIQUIDBEES.NS"
    ])

    # ─── BSE Stocks (additional) ───
    bse_stocks: List[str] = field(default_factory=lambda: [
        "RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "ICICIBANK.BO", "INFY.BO",
        "SBIN.BO", "HINDUNILVR.BO", "ITC.BO", "LT.BO", "KOTAKBANK.BO",
        "TATAMOTORS.BO", "MARUTI.BO", "WIPRO.BO", "HCLTECH.BO", "AXISBANK.BO",
        "SUNPHARMA.BO", "DRREDDY.BO", "CIPLA.BO", "LUPIN.BO", "DIVISLAB.BO",
        "JSWSTEEL.BO", "TATASTEEL.BO", "HINDALCO.BO", "VEDL.BO", "SAIL.BO",
        "ADANIENT.BO", "ADANIPORTS.BO", "ADANIGREEN.BO", "ADANITRANS.BO",
        "BAJFINANCE.BO", "BAJAJFINSV.BO", "HDFCLIFE.BO", "SBILIFE.BO",
        "ONGC.BO", "BPCL.BO", "IOC.BO", "GAIL.BO", "PETRONET.BO",
        "NTPC.BO", "POWERGRID.BO", "TATAPOWER.BO", "NHPC.BO"
    ])

    # Combined universe (NSE primary)
    universe_symbols: List[str] = field(default_factory=lambda: [])

    # Market context
    market_index: str = "^NSEI"
    bank_index: str = "^NSEBANK"
    volatility_index: str = "^INDIAVIX"
    lookback_days: int = 252
    feature_window: int = 60
    update_interval_seconds: int = 60

    def __post_init__(self):
        """Build combined universe"""
        seen = set()
        combined = (self.nse_largecap + self.nse_midcap +
                    self.nse_smallcap + self.bse_stocks + self.nse_etfs)
        for s in combined:
            if s not in seen:
                seen.add(s)
                self.universe_symbols.append(s)


@dataclass
class StrategyClusterConfig:
    """Strategy cluster definitions with Indian market regimes"""
    clusters: Dict[str, Dict] = field(default_factory=lambda: {
        "momentum": {
            "strategies": ["macd_histogram", "rsi_breakout", "adx_trend", "price_momentum", "volume_spike"],
            "allowed_regimes": ["bull_trend", "high_vol"],
            "weight": 1.0
        },
        "mean_reversion": {
            "strategies": ["bollinger_reversal", "rsi_oversold", "stochastic_crossover", "williams_r", "cci_extreme"],
            "allowed_regimes": ["range_bound", "low_vol"],
            "weight": 1.0
        },
        "volatility": {
            "strategies": ["atr_expansion", "vol_regime_switch", "straddle_arb", "gamma_scalp", "vix_contango"],
            "allowed_regimes": ["high_vol", "crash"],
            "weight": 0.8
        },
        "stat_arb": {
            "strategies": ["pairs_zscore", "cointegration_ou", "lead_lag", "triangular_arb", "dispersion"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 1.2
        },
        "microstructure": {
            "strategies": ["order_flow", "book_pressure", "vwap_deviation", "tick_cluster", "iceberg_detect"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 0.9
        },
        "ml_ai": {
            "strategies": ["lstm_predict", "rl_dqn", "anomaly_detect", "hdbscan_cluster", "gan_augment"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 1.1
        },
        "long_short_equity": {
            "strategies": ["cross_sectional_mom", "factor_ranking", "sector_rotation", "beta_neutral", "stub_trade"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 1.0
        },
        "event_driven": {
            "strategies": ["merger_arb", "convertible_arb", "earnings_vol", "special_situations", "distressed"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 1.0
        },
        "options_advanced": {
            "strategies": ["iron_condor", "butterfly", "calendar_spread", "ratio_spread", "diagonal_spread"],
            "allowed_regimes": ["range_bound", "low_vol", "bull_trend"],
            "weight": 0.8
        },
        "global_macro": {
            "strategies": ["cta_trend", "carry_trade", "macro_momentum", "fx_momentum"],
            "allowed_regimes": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
            "weight": 1.0
        }
    })


# ─── Indian Sector Classification ───
INDIAN_SECTORS = {
    "Banking": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "INDUSINDBK.NS", "BANKBARODA.NS", "CANBK.NS", "PNB.NS", "FEDERALBNK.NS",
        "IDFCFIRSTB.NS", "RBLBANK.NS", "UJJIVAN.NS", "EQUITAS.NS",
        "HDFCBANK.BO", "ICICIBANK.BO", "SBIN.BO", "KOTAKBANK.BO", "AXISBANK.BO"
    ],
    "IT & Technology": [
        "TCS.NS", "INFOSYS.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
        "PERSISTENT.NS", "COFORGE.NS", "LTIM.NS", "MPHASIS.NS", "OFSS.NS",
        "TATAELXSI.NS", "KPITTECH.NS", "LTTS.NS", "NAUKRI.NS",
        "TCS.BO", "INFOSYS.BO", "WIPRO.BO", "HCLTECH.BO"
    ],
    "Oil & Gas": [
        "RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "PETRONET.NS",
        "RELIANCE.BO", "ONGC.BO", "BPCL.BO", "IOC.BO", "GAIL.BO"
    ],
    "FMCG": [
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
        "GODREJCP.NS", "MARICO.NS", "DABUR.NS", "EMAMILTD.NS", "COLPAL.NS",
        "HINDUNILVR.BO", "ITC.BO"
    ],
    "Pharma": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "LUPIN.NS", "DIVISLAB.NS",
        "BIOCON.NS", "GLENMARK.NS", "ALKEM.NS", "TORNTPHARM.NS", "APOLLOHOSP.NS",
        "METROPOLIS.NS", "LALPATHLAB.NS",
        "SUNPHARMA.BO", "DRREDDY.BO", "CIPLA.BO", "LUPIN.BO"
    ],
    "Auto": [
        "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
        "EICHERMOT.NS", "TRENT.NS",
        "MARUTI.BO", "TATAMOTORS.BO"
    ],
    "Metals & Mining": [
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "SAIL.NS",
        "HINDCOPPER.NS", "NATIONALUM.NS", "MOIL.NS", "NMDC.NS",
        "TATASTEEL.BO", "JSWSTEEL.BO", "HINDALCO.BO", "VEDL.BO", "SAIL.BO"
    ],
    "Infrastructure": [
        "LT.NS", "ADANIPORTS.NS", "ADANIENT.NS", "GMRAIRPORT.NS", "CONCOR.NS",
        "IRCTC.NS", "BLUEDART.NS", "DELHIVERY.NS",
        "LT.BO", "ADANIPORTS.BO"
    ],
    "Power & Energy": [
        "NTPC.NS", "POWERGRID.NS", "TATAPOWER.NS", "NHPC.NS", "ADANIGREEN.NS",
        "COALINDIA.NS", "BHEL.NS",
        "NTPC.BO", "POWERGRID.BO"
    ],
    "Finance & NBFC": [
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "SHRIRAMFIN.NS", "ABCAPITAL.NS",
        "MANAPPURAM.NS", "LICI.NS", "HDFCLIFE.NS", "SBILIFE.NS",
        "BAJFINANCE.BO", "BAJAJFINSV.BO"
    ],
    "Cement": [
        "ULTRATECH.NS", "GRASIM.NS", "ASTRAL.NS", "APLAPOLLO.NS", "KAJARIACER.NS",
        "CERA.NS", "SUPREMEIND.NS"
    ],
    "Consumer Electronics": [
        "HAVELLS.NS", "VOLTAS.NS", "DIXON.NS", "AMBER.NS", "KAYNES.NS",
        "POLYCAB.NS", "WHIRLPOOL.NS"
    ],
    "Defence & Aerospace": [
        "HAL.NS", "BEL.NS", "BHEL.NS"
    ],
    "Retail & E-commerce": [
        "DMART.NS", "TRENT.NS", "ZOMATO.NS", "NYKAA.NS", "PAYTM.NS",
        "POLICYBZR.NS", "INDIAMART.NS", "JUSTDIAL.NS"
    ],
    "Paints": [
        "ASIANPAINT.NS", "BERGEPAINT.NS", "PIDILITIND.NS", "TITAN.NS"
    ],
    "ETF/Index": [
        "NIFTYBEES.NS", "BANKBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS",
        "ICICINIFTY.NS", "^NSEI", "^NSEBANK", "^CNXIT"
    ]
}

# Reverse lookup: symbol -> sector
SYMBOL_SECTOR_MAP = {}
for sector, symbols in INDIAN_SECTORS.items():
    for sym in symbols:
        SYMBOL_SECTOR_MAP[sym] = sector


# Global config instances
TRADING = TradingConfig()
RISK = RiskConfig()
REGIME = RegimeConfig()
DATA = DataConfig()
STRATEGY_CLUSTERS = StrategyClusterConfig()

# Server config
HOST = "0.0.0.0"
PORT = 8888

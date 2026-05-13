"""
AlphaBot v4.0 — Data Ingestion Engine (NSE/BSE India)
Fetches market data for Indian stocks using yfinance.
NSE symbols use .NS suffix, BSE use .BO suffix.
India VIX: ^INDIAVIX, Nifty50: ^NSEI, Bank Nifty: ^NSEBANK
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("alphabot.data")


def _safe_float(val):
    """Safely convert a value (possibly a pandas Series) to float"""
    try:
        if hasattr(val, 'item'):
            return float(val.item())
        if hasattr(val, 'iloc'):
            return float(val.iloc[0]) if len(val) > 0 else 0.0
        return float(val)
    except:
        return 0.0


def _flatten_columns(df):
    """Flatten multi-level columns from yfinance"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


class DataIngestionEngine:
    """
    Fetches and caches NSE/BSE market data.
    Uses yfinance (free) — NSE: SYMBOL.NS, BSE: SYMBOL.BO
    """

    def __init__(self, symbols: List[str], lookback_days: int = 252):
        self.symbols = symbols
        self.lookback_days = lookback_days
        self.cache: Dict[str, pd.DataFrame] = {}
        self.latest_prices: Dict[str, float] = {}
        self.india_vix_data: Optional[pd.DataFrame] = None
        self.nifty_data: Optional[pd.DataFrame] = None
        self.banknifty_data: Optional[pd.DataFrame] = None
        self.sector_map: Dict[str, str] = {}
        self.exchange_map: Dict[str, str] = {}   # symbol -> "NSE" or "BSE"
        self.last_update: Optional[datetime] = None
        self.executor = ThreadPoolExecutor(max_workers=6)
        self._initialized = False
        self._build_exchange_map()

    def _build_exchange_map(self):
        """Build exchange map from symbol suffixes"""
        for sym in self.symbols:
            if sym.endswith('.NS'):
                self.exchange_map[sym] = 'NSE'
            elif sym.endswith('.BO'):
                self.exchange_map[sym] = 'BSE'
            elif sym.startswith('^'):
                self.exchange_map[sym] = 'INDEX'
            else:
                self.exchange_map[sym] = 'NSE'

    async def initialize(self):
        """Load historical data for all symbols"""
        logger.info(f"Initializing NSE/BSE data for {len(self.symbols)} symbols...")
        loop = asyncio.get_event_loop()

        # Filter out index symbols for batch download
        tradable = [s for s in self.symbols if not s.startswith('^')]
        index_syms = [s for s in self.symbols if s.startswith('^')]

        # Download tradable symbols in batches
        batch_size = 15  # Smaller batches for Indian stocks
        for i in range(0, len(tradable), batch_size):
            batch = tradable[i:i + batch_size]
            await loop.run_in_executor(self.executor, self._download_batch, batch)
            await asyncio.sleep(0.5)  # Rate limit respect

        # Download indices
        await loop.run_in_executor(self.executor, self._download_indices)

        # Build sector map
        from config import SYMBOL_SECTOR_MAP
        self.sector_map = SYMBOL_SECTOR_MAP.copy()

        self._initialized = True
        self.last_update = datetime.utcnow()
        nse_count = sum(1 for s in self.cache if s.endswith('.NS'))
        bse_count = sum(1 for s in self.cache if s.endswith('.BO'))
        logger.info(f"Data initialized: {len(self.cache)} symbols (NSE:{nse_count}, BSE:{bse_count})")

    def _download_batch(self, symbols: List[str]):
        """Download historical OHLCV data for a batch"""
        try:
            end = datetime.now()
            start = end - timedelta(days=self.lookback_days + 30)

            if len(symbols) == 1:
                data = yf.download(
                    symbols[0], start=start.strftime('%Y-%m-%d'),
                    end=end.strftime('%Y-%m-%d'), auto_adjust=True,
                    progress=False
                )
                sym = symbols[0]
                if not data.empty:
                    data = _flatten_columns(data)
                    # Ensure standard columns
                    data = self._standardize_df(data)
                    if len(data) >= 20:
                        self.cache[sym] = data.copy()
                        self.latest_prices[sym] = _safe_float(data['Close'].iloc[-1])
            else:
                data = yf.download(
                    symbols, start=start.strftime('%Y-%m-%d'),
                    end=end.strftime('%Y-%m-%d'), group_by='ticker',
                    auto_adjust=True, threads=True, progress=False
                )
                for sym in symbols:
                    try:
                        if isinstance(data.columns, pd.MultiIndex):
                            if sym in data.columns.get_level_values(0):
                                df = data[sym].dropna(how='all')
                            else:
                                continue
                        else:
                            continue
                        df = self._standardize_df(df)
                        if not df.empty and len(df) >= 20:
                            self.cache[sym] = df.copy()
                            self.latest_prices[sym] = _safe_float(df['Close'].iloc[-1])
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"Batch download error: {e}")

    def _standardize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure DataFrame has standard OHLCV columns"""
        if df is None or df.empty:
            return df
        # Rename columns if needed
        rename_map = {}
        for col in df.columns:
            col_lower = str(col).lower()
            if 'open' in col_lower: rename_map[col] = 'Open'
            elif 'high' in col_lower: rename_map[col] = 'High'
            elif 'low' in col_lower: rename_map[col] = 'Low'
            elif 'close' in col_lower: rename_map[col] = 'Close'
            elif 'volume' in col_lower: rename_map[col] = 'Volume'
        if rename_map:
            df = df.rename(columns=rename_map)
        # Keep only OHLCV
        keep = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        df = df[keep].copy()
        # Drop rows with NaN Close
        df = df.dropna(subset=['Close'])
        return df

    def _download_indices(self):
        """Download India VIX, Nifty 50, Bank Nifty"""
        end = datetime.now()
        start = end - timedelta(days=self.lookback_days + 30)

        indices = {
            "^INDIAVIX": "india_vix_data",
            "^NSEI": "nifty_data",
            "^NSEBANK": "banknifty_data",
            "^BSESN": "sensex_data"
        }
        for ticker, attr in indices.items():
            try:
                df = yf.download(ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'),
                                 progress=False, auto_adjust=True)
                if not df.empty:
                    df = _flatten_columns(df)
                    df = self._standardize_df(df)
                    setattr(self, attr, df)
                    self.cache[ticker] = df
                    self.latest_prices[ticker] = _safe_float(df['Close'].iloc[-1])
                    logger.info(f"Loaded {ticker}: {_safe_float(df['Close'].iloc[-1]):.2f}")
            except Exception as e:
                logger.debug(f"Index {ticker} failed: {e}")

    # ─── Getters ───────────────────────────────────────────────────
    def get_ohlcv(self, symbol: str, days: int = 60) -> Optional[pd.DataFrame]:
        if symbol in self.cache:
            df = self.cache[symbol].tail(days)
            return df if len(df) >= 5 else None
        return None

    def get_closes(self, symbol: str, days: int = 60) -> Optional[np.ndarray]:
        df = self.get_ohlcv(symbol, days)
        if df is not None and 'Close' in df.columns:
            return df['Close'].values.astype(float)
        return None

    def get_latest_price(self, symbol: str) -> float:
        return self.latest_prices.get(symbol, 0.0)

    def get_india_vix(self) -> float:
        """India VIX (typically 10-40, crash >35)"""
        if self.india_vix_data is not None and not self.india_vix_data.empty:
            return _safe_float(self.india_vix_data['Close'].iloc[-1])
        # Fallback to cached ^INDIAVIX
        if "^INDIAVIX" in self.cache:
            return _safe_float(self.cache["^INDIAVIX"]['Close'].iloc[-1])
        return 15.0

    def get_nifty_price(self) -> float:
        if self.nifty_data is not None and not self.nifty_data.empty:
            return _safe_float(self.nifty_data['Close'].iloc[-1])
        return self.latest_prices.get("^NSEI", 0.0)

    def get_nifty_ema200(self) -> float:
        if self.nifty_data is not None and len(self.nifty_data) >= 200:
            return _safe_float(self.nifty_data['Close'].ewm(span=200).mean().iloc[-1])
        elif self.nifty_data is not None and len(self.nifty_data) > 0:
            return _safe_float(self.nifty_data['Close'].ewm(span=min(200, len(self.nifty_data))).mean().iloc[-1])
        return 0.0

    def get_banknifty_price(self) -> float:
        if self.banknifty_data is not None and not self.banknifty_data.empty:
            return _safe_float(self.banknifty_data['Close'].iloc[-1])
        return 0.0

    def get_sensex_price(self) -> float:
        if getattr(self, 'sensex_data', None) is not None and not self.sensex_data.empty:
            return _safe_float(self.sensex_data['Close'].iloc[-1])
        return self.latest_prices.get("^BSESN", 0.0)

    def get_sector(self, symbol: str) -> str:
        return self.sector_map.get(symbol, "Unknown")

    def get_exchange(self, symbol: str) -> str:
        return self.exchange_map.get(symbol, "NSE")

    def get_available_symbols(self) -> List[str]:
        """Return tradable symbols (exclude index tickers)"""
        return [
            s for s in self.cache
            if not s.startswith('^') and
               (s.endswith('.NS') or s.endswith('.BO')) and
               len(self.cache[s]) >= 20
        ]

    def get_nse_symbols(self) -> List[str]:
        return [s for s in self.get_available_symbols() if s.endswith('.NS')]

    def get_bse_symbols(self) -> List[str]:
        return [s for s in self.get_available_symbols() if s.endswith('.BO')]

    def get_returns(self, symbol: str, days: int = 20) -> Optional[np.ndarray]:
        closes = self.get_closes(symbol, days + 1)
        if closes is not None and len(closes) > 1:
            return np.diff(np.log(np.maximum(closes, 0.001)))
        return None

    def get_display_name(self, symbol: str) -> str:
        """Clean display name (remove .NS/.BO suffix)"""
        return symbol.replace('.NS', '').replace('.BO', '')

    async def refresh(self):
        """Refresh latest prices for top symbols"""
        loop = asyncio.get_event_loop()
        symbols = self.get_available_symbols()[:30]

        def _refresh():
            for sym in symbols[:15]:
                try:
                    tk = yf.Ticker(sym)
                    info = tk.fast_info
                    if hasattr(info, 'last_price') and info.last_price:
                        self.latest_prices[sym] = float(info.last_price)
                except Exception:
                    pass

        try:
            await loop.run_in_executor(self.executor, _refresh)
            self.last_update = datetime.utcnow()
        except Exception as e:
            logger.debug(f"Refresh error: {e}")

"""
AlphaBot v4.0 — News Intelligence Engine (NSE/BSE India)
Fetches market-moving news from official Indian financial news sources.
Sources: Economic Times, Moneycontrol, Business Standard, LiveMint, NSE/BSE RSS
"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("alphabot.news")

# ─── News Sources ───────────────────────────────────────────────
NEWS_SOURCES = [
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rss.cms",
        "type": "rss",
        "weight": 1.2
    },
    {
        "name": "Moneycontrol Latest",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml",
        "type": "rss",
        "weight": 1.1
    },
    {
        "name": "Business Standard Markets",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
        "type": "rss",
        "weight": 1.1
    },
    {
        "name": "LiveMint Markets",
        "url": "https://www.livemint.com/rss/markets",
        "type": "rss",
        "weight": 1.0
    },
    {
        "name": "Financial Express Markets",
        "url": "https://www.financialexpress.com/market/feed/",
        "type": "rss",
        "weight": 1.0
    },
    {
        "name": "NDTV Profit",
        "url": "https://www.ndtvprofit.com/markets/rss",
        "type": "rss",
        "weight": 0.9
    },
]

# ─── Sentiment Keyword Dictionaries ─────────────────────────────
BULLISH_KEYWORDS = {
    # Strong bullish (weight 2)
    "strong": ["surge", "soar", "rally", "breakout", "beat", "record high", "upgrade",
               "outperform", "strong buy", "bullish", "profit rises", "revenue growth",
               "dividend", "buyback", "acquisition", "merger", "deal", "contract win",
               "expansion", "positive outlook", "raised guidance", "order win"],
    # Moderate bullish (weight 1)
    "moderate": ["gain", "rise", "up", "positive", "growth", "recovery", "improve",
                 "higher", "support", "benefit", "opportunity", "momentum", "inflow"]
}
BEARISH_KEYWORDS = {
    # Strong bearish (weight 2)
    "strong": ["crash", "plunge", "collapse", "downgrade", "sell", "bearish", "loss",
               "miss", "warning", "risk", "fraud", "probe", "investigation", "ban",
               "recall", "penalty", "fine", "default", "bankruptcy", "layoff",
               "profit warning", "guidance cut", "negative outlook", "debt"],
    # Moderate bearish (weight 1)
    "moderate": ["fall", "drop", "decline", "lower", "pressure", "weak", "concern",
                 "uncertainty", "challenge", "headwind", "outflow", "sell-off", "caution"]
}

MACRO_KEYWORDS = ["rbi", "sebi", "nifty", "sensex", "fed", "inflation", "gdp", "interest rate",
                  "budget", "policy", "crude oil", "rupee", "dollar", "fii", "dii", "monsoon",
                  "repo rate", "cpi", "iip", "trade deficit", "current account"]

SECTOR_KEYWORDS = {
    "Banking": ["bank", "banking", "npa", "credit", "loan", "deposit", "nbfc", "rbi policy"],
    "IT & Technology": ["it sector", "tech", "software", "digital", "ai", "cloud", "tcs", "infosys", "wipro"],
    "Pharma": ["pharma", "drug", "fda", "usfda", "medicine", "clinical", "biotech"],
    "Oil & Gas": ["crude", "oil", "gas", "ongc", "reliance", "petrol", "opec"],
    "Auto": ["auto", "vehicle", "ev", "electric vehicle", "sales", "automobile"],
    "Metals & Mining": ["steel", "metal", "aluminium", "copper", "iron ore", "mining"],
    "FMCG": ["fmcg", "consumer", "retail", "fmcg sales", "rural", "urban"],
    "Power & Energy": ["power", "energy", "electricity", "solar", "renewable", "ntpc"],
}


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published: str
    sentiment_score: float  # -1 to +1
    sentiment_label: str    # BULLISH, BEARISH, NEUTRAL
    impact: str             # HIGH, MEDIUM, LOW
    affected_symbols: List[str] = field(default_factory=list)
    affected_sectors: List[str] = field(default_factory=list)
    is_macro: bool = False
    news_id: str = ""

    def __post_init__(self):
        if not self.news_id:
            self.news_id = hashlib.md5(self.title.encode()).hexdigest()[:8]

    def to_dict(self):
        return {
            "id": self.news_id,
            "title": self.title,
            "summary": self.summary[:200] if self.summary else "",
            "url": self.url,
            "source": self.source,
            "published": self.published,
            "sentiment": self.sentiment_label,
            "sentiment_score": round(self.sentiment_score, 3),
            "impact": self.impact,
            "affected_symbols": self.affected_symbols,
            "affected_sectors": self.affected_sectors,
            "is_macro": self.is_macro
        }


class NewsEngine:
    """Fetches and analyzes market news from Indian financial sources"""

    def __init__(self):
        self.news_cache: List[NewsItem] = []
        self.symbol_news: Dict[str, List[NewsItem]] = {}
        self.sector_news: Dict[str, List[NewsItem]] = {}
        self.macro_news: List[NewsItem] = []
        self.market_sentiment: float = 0.0  # -1 to +1
        self.last_fetch: Optional[datetime] = None
        self.fetch_interval_minutes = 15
        self._session: Optional[aiohttp.ClientSession] = None
        self._known_ids = set()

        # Build reverse map: stock name → symbol
        self.name_to_symbol = self._build_name_map()

    def _build_name_map(self) -> Dict[str, str]:
        """Maps company names to NSE symbols"""
        return {
            "tcs": "TCS.NS", "tata consultancy": "TCS.NS",
            "infosys": "INFY.NS", "infy": "INFY.NS",
            "reliance": "RELIANCE.NS", "ril": "RELIANCE.NS",
            "hdfc bank": "HDFCBANK.NS", "hdfcbank": "HDFCBANK.NS",
            "icici bank": "ICICIBANK.NS", "icicibank": "ICICIBANK.NS",
            "sbi": "SBIN.NS", "state bank": "SBIN.NS",
            "wipro": "WIPRO.NS",
            "hcl tech": "HCLTECH.NS", "hcltech": "HCLTECH.NS",
            "bharti airtel": "BHARTIARTL.NS", "airtel": "BHARTIARTL.NS",
            "itc": "ITC.NS",
            "larsen": "LT.NS", "l&t": "LT.NS",
            "axis bank": "AXISBANK.NS", "axisbank": "AXISBANK.NS",
            "kotak": "KOTAKBANK.NS", "kotak mahindra": "KOTAKBANK.NS",
            "bajaj finance": "BAJFINANCE.NS",
            "maruti": "MARUTI.NS", "maruti suzuki": "MARUTI.NS",
            "asian paint": "ASIANPAINT.NS",
            "sun pharma": "SUNPHARMA.NS", "sun pharmaceutical": "SUNPHARMA.NS",
            "dr reddy": "DRREDDY.NS", "dr. reddy": "DRREDDY.NS",
            "cipla": "CIPLA.NS",
            "titan": "TITAN.NS",
            "tata motors": "TATAMOTORS.NS",
            "ongc": "ONGC.NS",
            "ntpc": "NTPC.NS",
            "power grid": "POWERGRID.NS",
            "coal india": "COALINDIA.NS",
            "tech mahindra": "TECHM.NS",
            "adani": "ADANIENT.NS",
            "adani ports": "ADANIPORTS.NS",
            "nestle": "NESTLEIND.NS",
            "britannia": "BRITANNIA.NS",
            "hindalco": "HINDALCO.NS",
            "jswsteel": "JSWSTEEL.NS", "jsw steel": "JSWSTEEL.NS",
            "tata steel": "TATASTEEL.NS",
            "bpcl": "BPCL.NS", "bharat petroleum": "BPCL.NS",
            "zomato": "ZOMATO.NS",
            "paytm": "PAYTM.NS",
            "hal": "HAL.NS", "hindustan aeronautics": "HAL.NS",
            "irctc": "IRCTC.NS",
            "dmart": "DMART.NS", "avenue supermarts": "DMART.NS",
            "bajaj auto": "BAJAJ-AUTO.NS",
            "hero motocorp": "HEROMOTOCO.NS",
            "eicher": "EICHERMOT.NS",
            "divis lab": "DIVISLAB.NS",
        }

    async def initialize(self):
        """Initial fetch"""
        await self.fetch_all_news()
        logger.info(f"News engine initialized: {len(self.news_cache)} articles loaded")

    async def fetch_all_news(self):
        """Fetch news from all sources"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 AlphaBot/4.0 News Reader',
                'Accept': 'application/rss+xml, application/xml, text/xml'
            }
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                tasks = [self._fetch_rss(session, src) for src in NEWS_SOURCES]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            new_items = []
            for result in results:
                if isinstance(result, list):
                    new_items.extend(result)

            # Deduplicate
            fresh = [item for item in new_items if item.news_id not in self._known_ids]
            for item in fresh:
                self._known_ids.add(item.news_id)

            # Add to cache (keep last 200)
            self.news_cache = (fresh + self.news_cache)[:200]

            # Index by symbol and sector
            self._index_news(fresh)

            # Calculate overall market sentiment
            self._calculate_market_sentiment()

            self.last_fetch = datetime.utcnow()
            if fresh:
                logger.info(f"News: +{len(fresh)} new articles | Market sentiment: {self.market_sentiment:+.2f}")

        except Exception as e:
            logger.warning(f"News fetch error: {e}")

    async def _fetch_rss(self, session: aiohttp.ClientSession, source: dict) -> List[NewsItem]:
        """Fetch and parse RSS feed"""
        items = []
        try:
            async with session.get(source['url'], ssl=False) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text(errors='replace')

            root = ET.fromstring(text)
            channel = root.find('channel') or root

            entries = channel.findall('item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')

            for entry in entries[:15]:  # Max 15 per source
                title = self._get_text(entry, ['title'])
                summary = self._get_text(entry, ['description', 'summary', 'content'])
                url = self._get_text(entry, ['link', 'guid'])
                published = self._get_text(entry, ['pubDate', 'published', 'dc:date'])

                if not title:
                    continue

                # Clean text
                title = self._clean_html(title)
                summary = self._clean_html(summary or "")

                # Analyze sentiment
                sentiment = self._analyze_sentiment(title + " " + summary)
                affected_syms = self._find_affected_symbols(title + " " + summary)
                affected_secs = self._find_affected_sectors(title + " " + summary)
                is_macro = any(kw in (title + summary).lower() for kw in MACRO_KEYWORDS)
                impact = self._assess_impact(title, sentiment, is_macro, affected_syms)

                item = NewsItem(
                    title=title,
                    summary=summary[:500],
                    url=url or "",
                    source=source['name'],
                    published=published or datetime.utcnow().isoformat(),
                    sentiment_score=sentiment,
                    sentiment_label="BULLISH" if sentiment > 0.1 else "BEARISH" if sentiment < -0.1 else "NEUTRAL",
                    impact=impact,
                    affected_symbols=affected_syms,
                    affected_sectors=affected_secs,
                    is_macro=is_macro
                )
                items.append(item)

        except Exception as e:
            logger.debug(f"RSS {source['name']}: {e}")

        return items

    def _get_text(self, element, tags: List[str]) -> Optional[str]:
        for tag in tags:
            el = element.find(tag)
            if el is not None and el.text:
                return el.text.strip()
        return None

    def _clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:500]

    def _analyze_sentiment(self, text: str) -> float:
        """Score text sentiment -1 to +1"""
        text_lower = text.lower()
        score = 0.0

        for kw in BULLISH_KEYWORDS['strong']:
            if kw in text_lower:
                score += 2.0
        for kw in BULLISH_KEYWORDS['moderate']:
            if kw in text_lower:
                score += 1.0
        for kw in BEARISH_KEYWORDS['strong']:
            if kw in text_lower:
                score -= 2.0
        for kw in BEARISH_KEYWORDS['moderate']:
            if kw in text_lower:
                score -= 1.0

        # Normalize to -1..+1
        return max(-1.0, min(1.0, score / 6.0))

    def _find_affected_symbols(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for name, sym in self.name_to_symbol.items():
            if name in text_lower and sym not in found:
                found.append(sym)
        return found[:5]

    def _find_affected_sectors(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found.append(sector)
        return found[:3]

    def _assess_impact(self, title: str, sentiment: float, is_macro: bool, symbols: List[str]) -> str:
        abs_s = abs(sentiment)
        if is_macro or abs_s > 0.5 or len(symbols) > 2:
            return "HIGH"
        elif abs_s > 0.2 or symbols:
            return "MEDIUM"
        return "LOW"

    def _index_news(self, items: List[NewsItem]):
        for item in items:
            for sym in item.affected_symbols:
                self.symbol_news.setdefault(sym, []).insert(0, item)
                self.symbol_news[sym] = self.symbol_news[sym][:20]
            for sec in item.affected_sectors:
                self.sector_news.setdefault(sec, []).insert(0, item)
                self.sector_news[sec] = self.sector_news[sec][:20]
            if item.is_macro:
                self.macro_news.insert(0, item)
                self.macro_news = self.macro_news[:30]

    def _calculate_market_sentiment(self):
        """Overall market sentiment from recent news"""
        if not self.news_cache:
            self.market_sentiment = 0.0
            return
        recent = self.news_cache[:30]
        scores = [n.sentiment_score * (2 if n.impact == 'HIGH' else 1.5 if n.impact == 'MEDIUM' else 1) for n in recent]
        self.market_sentiment = sum(scores) / max(len(scores), 1)

    def get_symbol_sentiment(self, symbol: str) -> Dict:
        """Get news sentiment for a specific symbol"""
        news = self.symbol_news.get(symbol, [])
        # Also check sector news
        sector_items = []
        for sec_news in self.sector_news.values():
            sector_items.extend(sec_news[:3])

        all_items = news + [n for n in sector_items if n not in news][:5]
        if not all_items:
            return {"score": 0.0, "label": "NEUTRAL", "count": 0, "headlines": []}

        score = sum(n.sentiment_score for n in all_items) / len(all_items)
        return {
            "score": round(score, 3),
            "label": "BULLISH" if score > 0.1 else "BEARISH" if score < -0.1 else "NEUTRAL",
            "count": len(all_items),
            "headlines": [n.title for n in all_items[:3]]
        }

    def get_latest_news(self, n: int = 30) -> List[Dict]:
        return [item.to_dict() for item in self.news_cache[:n]]

    def get_high_impact_news(self, n: int = 10) -> List[Dict]:
        high = [item for item in self.news_cache if item.impact == 'HIGH']
        return [item.to_dict() for item in high[:n]]

    def get_symbol_news(self, symbol: str, n: int = 10) -> List[Dict]:
        return [item.to_dict() for item in self.symbol_news.get(symbol, [])[:n]]

    def should_refresh(self) -> bool:
        if not self.last_fetch:
            return True
        return (datetime.utcnow() - self.last_fetch).seconds > self.fetch_interval_minutes * 60

"""
AlphaBot v4.0 — Screener.in Fundamentals Engine
Fetches deep fundamental data (P/E, ROCE, ROE, Debt) from screener.in
Used to factor into Intraday & Swing recommendations.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Optional
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger("alphabot.screener")

class ScreenerEngine:
    """Scrapes basic fundamental ratios from screener.in for NSE/BSE stocks"""
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.last_update: Dict[str, datetime] = {}
        self.cache_ttl_hours = 24  # Fundamentals don't change often intraday
        self._session = None

    async def initialize(self):
        logger.info("ScreenerEngine initialized")

    def _clean_value(self, val_str: str) -> float:
        """Clean string values like '24.5 %' or '₹ 1,234 Cr.' to float"""
        try:
            cleaned = re.sub(r'[^\d.-]', '', val_str)
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0

    async def fetch_fundamentals(self, symbol: str) -> Optional[Dict]:
        """Fetch fundamental data for a specific symbol"""
        # Clean symbol (e.g., RELIANCE.NS -> RELIANCE)
        base_sym = symbol.replace('.NS', '').replace('.BO', '')
        
        # Check cache
        if base_sym in self.cache:
            last_time = self.last_update.get(base_sym)
            if last_time and (datetime.utcnow() - last_time) < timedelta(hours=self.cache_ttl_hours):
                return self.cache[base_sym]

        url = f"https://www.screener.in/company/{base_sym}/consolidated/"
        fallback_url = f"https://www.screener.in/company/{base_sym}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        try:
            if not self._session:
                self._session = aiohttp.ClientSession(headers=headers)
            
            async with self._session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    # Try fallback (standalone instead of consolidated)
                    async with self._session.get(fallback_url, timeout=10) as fallback_resp:
                        if fallback_resp.status != 200:
                            return None
                        html = await fallback_resp.text()
                else:
                    html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            ratios_div = soup.find('div', class_='company-ratios')
            
            if not ratios_div:
                return None
                
            data = {'symbol': symbol}
            
            # Map of common screener fields to our standard names
            field_map = {
                'Market Cap': 'market_cap',
                'Stock P/E': 'pe_ratio',
                'ROCE': 'roce',
                'ROE': 'roe',
                'Debt to equity': 'debt_to_equity',
                'Dividend Yield': 'div_yield',
                'Book Value': 'book_value',
                'Face Value': 'face_value',
                'PEG Ratio': 'peg_ratio',
                'Price to book value': 'pb_ratio',
                'Promoter holding': 'promoter_holding'
            }
            
            list_items = ratios_div.find_all('li')
            for li in list_items:
                name_span = li.find('span', class_='name')
                val_span = li.find('span', class_='number')
                if name_span and val_span:
                    name = name_span.text.strip()
                    val = val_span.text.strip()
                    for key, std_name in field_map.items():
                        if key.lower() in name.lower():
                            data[std_name] = self._clean_value(val)
                            break
            
            # Extract pros/cons
            pros_div = soup.find('div', class_='pros')
            cons_div = soup.find('div', class_='cons')
            data['pros'] = [li.text.strip() for li in pros_div.find_all('li')] if pros_div else []
            data['cons'] = [li.text.strip() for li in cons_div.find_all('li')] if cons_div else []
            
            # Fundamentals Score (0-100)
            score = 50
            if data.get('roce', 0) > 20: score += 10
            elif data.get('roce', 0) < 10: score -= 10
            
            if data.get('roe', 0) > 15: score += 10
            elif data.get('roe', 0) < 10: score -= 10
            
            if 0 < data.get('pe_ratio', 100) < 25: score += 10
            elif data.get('pe_ratio', 0) > 50: score -= 10
            
            if data.get('debt_to_equity', 1) < 0.5: score += 10
            elif data.get('debt_to_equity', 0) > 1.5: score -= 10
            
            if data.get('promoter_holding', 0) > 50: score += 10
            
            data['fundamental_score'] = max(0, min(100, score))
            
            # Cache it
            self.cache[base_sym] = data
            self.last_update[base_sym] = datetime.utcnow()
            
            return data
            
        except Exception as e:
            logger.debug(f"Screener fetch error for {symbol}: {e}")
            return None

    async def close(self):
        if self._session:
            await self._session.close()

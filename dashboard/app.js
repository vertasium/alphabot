/**
 * AlphaBot v4.0 — Prediction & News Dashboard Frontend
 */

let ws = null;
let reconnectAttempts = 0;
let equityCurve = [];
let allRankings = [];
let allPredictions = [];
let allNews = [];
let currentRecFilter = 'all';
let currentNewsFilter = 'all';

// Tabs
function showTab(tabId, el) {
    document.querySelectorAll('.tab-page').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('page-' + tabId).style.display = 'block';
    if (el) el.classList.add('active');
    if(tabId === 'dashboard') drawChart();
}

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/live`);
    ws.onopen = () => { reconnectAttempts = 0; setStatus(true); };
    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'cycle_update') onCycleUpdate(data);
            if (data.type === 'fast_tick') onFastTick(data);
        } catch(err) {}
    };
    ws.onclose = () => {
        setStatus(false);
        if (reconnectAttempts++ < 60) setTimeout(connectWebSocket, 3000);
    };
}

function setStatus(live) {
    document.getElementById('statusDot').className = `status-dot ${live?'live':'stopped'}`;
    document.getElementById('statusText').textContent = live ? 'LIVE' : 'RECONNECTING...';
}

function onCycleUpdate(data) {
    const p = data.portfolio || {};
    const m = data.market || {};
    
    // Header & Ticker
    const niftyVal = m.nifty50 || lastPrices["^NSEI"] || 0;
    if (niftyVal > 0) setText('hNifty', niftyVal.toLocaleString('en-IN'));
    setText('hNiftyChg', fmt(m.nifty_change||0, 2, '%'));
    document.getElementById('hNiftyChg').className = `ticker-chg ${m.nifty_change>=0?'positive':'negative'}`;
    const sensexVal = m.sensex || lastPrices["^BSESN"] || 0;
    if (sensexVal > 0) setText('hSensex', sensexVal.toLocaleString('en-IN'));
    const bankNiftyVal = m.banknifty || lastPrices["^NSEBANK"] || 0;
    if (bankNiftyVal > 0) setText('hBankNifty', bankNiftyVal.toLocaleString('en-IN'));
    setText('hVix', (m.india_vix||15).toFixed(1));
    const ns = data.news_sentiment || 0;
    setText('hNewsSentiment', ns > 0.1 ? 'BULLISH' : ns < -0.1 ? 'BEARISH' : 'NEUTRAL');
    
    setText('nseCount', `NSE: ${data.nse_count||0}`);
    setText('bseCount', `BSE: ${data.bse_count||0}`);
    setText('newsCount', `NEWS: ${data.news_count||0}`);
    
    const reg = (data.regime||'').replace('_',' ').toUpperCase();
    document.getElementById('regimeBadge').textContent = reg;
    document.getElementById('regimeBadge').className = 'regime-badge ' + (reg.includes('BULL')?'regime-bull':reg.includes('BEAR')?'regime-bear':'regime-neutral');

    // Dashboard Stats
    setText('equity', formatINR(p.equity||50000000));
    setText('equityChange', fmt(p.total_pnl_pct||0, 2, '%'));
    setClass('equityChange', p.total_pnl_pct);
    setText('dailyPnl', formatINRSigned(p.daily_pnl||0));
    setClass('dailyPnl', p.daily_pnl);
    setText('totalPnl', `Total: ${formatINRSigned(p.total_pnl||0)}`);
    setText('sharpe', (p.sharpe_ratio||0).toFixed(2));
    setText('winRate', `Win Rate: ${((p.win_rate||0)*100).toFixed(0)}%`);
    setText('vixValue', (m.india_vix||15).toFixed(1));
    document.getElementById('vixPointer').style.left = Math.min((m.india_vix||15)/45*100, 98) + '%';
    setText('drawdown', `Max DD: ${((p.drawdown_pct||0)*100).toFixed(2)}%`);

    // Market Bar
    if (niftyVal > 0) setText('mbNifty', niftyVal.toLocaleString('en-IN'));
    setText('mbNiftyChg', fmt(m.nifty_change||0, 2, '%'));
    setClass('mbNiftyChg', m.nifty_change);
    if (sensexVal > 0) setText('mbSensex', sensexVal.toLocaleString('en-IN'));
    if (bankNiftyVal > 0) setText('mbBankNifty', bankNiftyVal.toLocaleString('en-IN'));
    setText('mbVix', (m.india_vix||15).toFixed(1));
    setText('mbRegime', reg);
    setText('mbNewsSentiment', ns>0.1?'BULLISH':ns<-0.1?'BEARISH':'NEUTRAL');
    setText('mbSignals', data.confirmed||0);
    setText('mbPredictions', data.predictions||0);
    setText('mbPositions', p.num_positions||0);
    setText('mbCycle', `#${data.cycle||0}`);

    // Update Arrays
    if (data.rankings) allRankings = data.rankings;
    if (data.top_recommendations) renderRecommendations(data.top_recommendations);
    if (data.outlook && data.outlook.date) renderOutlook(data.outlook);
    if (data.intraday_calls) renderIntraday(data.intraday_calls);
    
    equityCurve.push(p.equity||50000000);
    if(equityCurve.length > 200) equityCurve = equityCurve.slice(-200);
    drawChart();

    fetchDataAsync(); // Poll rest
}

let lastPrices = {};
function flashElement(id, color) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.transition = 'none';
    el.style.backgroundColor = color === 'green' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)';
    setTimeout(() => {
        el.style.transition = 'background-color 1s ease';
        el.style.backgroundColor = 'transparent';
    }, 100);
}

function onFastTick(data) {
    const prices = data.prices;
    if (prices["^NSEI"]) {
        const p = prices["^NSEI"];
        if (lastPrices["^NSEI"] && p !== lastPrices["^NSEI"]) {
            flashElement('hNifty', p > lastPrices["^NSEI"] ? 'green' : 'red');
            flashElement('mbNifty', p > lastPrices["^NSEI"] ? 'green' : 'red');
        }
        setText('hNifty', p.toLocaleString('en-IN'));
        setText('mbNifty', p.toLocaleString('en-IN'));
        lastPrices["^NSEI"] = p;
    }
    if (prices["^BSESN"]) {
        const p = prices["^BSESN"];
        if (lastPrices["^BSESN"] && p !== lastPrices["^BSESN"]) {
            flashElement('hSensex', p > lastPrices["^BSESN"] ? 'green' : 'red');
            flashElement('mbSensex', p > lastPrices["^BSESN"] ? 'green' : 'red');
        }
        setText('hSensex', p.toLocaleString('en-IN'));
        setText('mbSensex', p.toLocaleString('en-IN'));
        lastPrices["^BSESN"] = p;
    }
    if (prices["^NSEBANK"]) {
        const p = prices["^NSEBANK"];
        if (lastPrices["^NSEBANK"] && p !== lastPrices["^NSEBANK"]) {
            flashElement('hBankNifty', p > lastPrices["^NSEBANK"] ? 'green' : 'red');
            flashElement('mbBankNifty', p > lastPrices["^NSEBANK"] ? 'green' : 'red');
        }
        setText('hBankNifty', p.toLocaleString('en-IN'));
        setText('mbBankNifty', p.toLocaleString('en-IN'));
        lastPrices["^NSEBANK"] = p;
    }
    if (prices["^INDIAVIX"]) {
        setText('hVix', prices["^INDIAVIX"].toFixed(1));
        setText('mbVix', prices["^INDIAVIX"].toFixed(1));
    }
    
    // Position updates
    const tbody = document.getElementById('positionsBody');
    if (tbody) {
        const rows = tbody.querySelectorAll('tr');
        rows.forEach(r => {
            const symEl = r.querySelector('strong');
            if (symEl) {
                const sym = symEl.textContent + (r.querySelector('.nse') ? '.NS' : '.BO');
                if (prices[sym]) {
                    const priceCell = r.cells[4]; // LTP column
                    const oldPrice = parseFloat(priceCell.textContent);
                    if (!isNaN(oldPrice) && oldPrice !== prices[sym]) {
                        priceCell.textContent = prices[sym].toFixed(2);
                        flashElement(priceCell.id || (priceCell.id = 'pos_'+sym), prices[sym] > oldPrice ? 'green' : 'red');
                    }
                }
            }
        });
    }
}

async function fetchDataAsync() {
    try {
        const [pos, sigs, trd, agt, sec, pred, news, lrn] = await Promise.all([
            fetch('/api/v4/positions').then(r=>r.json()),
            fetch('/api/v4/signals').then(r=>r.json()),
            fetch('/api/v4/trades').then(r=>r.json()),
            fetch('/api/v4/agents').then(r=>r.json()),
            fetch('/api/v4/sectors').then(r=>r.json()),
            fetch('/api/v4/predictions').then(r=>r.json()),
            fetch('/api/v4/news').then(r=>r.json()),
            fetch('/api/v4/learning/stats').then(r=>r.json())
        ]);
        renderPositions(pos);
        renderTrades(trd);
        renderAgents(agt);
        renderSectors(sec);
        allPredictions = pred; filterPredictions();
        renderPatterns(pred);
        allNews = news; filterNews(currentNewsFilter);
        updateNewsStats(news);
        if(lrn) renderLearningTab(lrn);
    } catch(e) {}
}

function renderRecommendations(recs) {
    const grid = document.getElementById('recommendationsGrid');
    if (!recs || !recs.length) return grid.innerHTML = '<div style="padding:20px;color:var(--text-dim)">No recommendations yet</div>';
    
    let filtered = recs;
    if (currentRecFilter === 'BUY') filtered = recs.filter(r => r.action==='BUY');
    else if (currentRecFilter === 'SELL') filtered = recs.filter(r => r.action==='SELL SHORT');
    else if (currentRecFilter === 'A') filtered = recs.filter(r => ['A+','A'].includes(r.confidence_grade));

    grid.innerHTML = filtered.map(r => {
        const isBuy = r.action === 'BUY';
        const color = isBuy ? '#10b981' : '#ef4444';
        const gClass = r.confidence_grade.replace('+','p');
        
        return `<div class="rec-card ${isBuy?'buy':'sell'}">
            <div class="rec-header">
                <div>
                    <div class="rec-symbol">${r.display} <span style="font-size:10px;color:var(--text-dim);font-weight:400">${r.exchange}</span></div>
                    <div style="font-size:10px;color:${color};font-weight:700;margin-top:2px">${r.action} (Prob: ${r.direction_probability}%)</div>
                </div>
                <div class="rec-grade ${gClass}">${r.confidence_grade}</div>
            </div>
            <div class="rec-meta">
                <span class="rec-sector">${r.sector}</span>
                <span style="font-size:9px;color:var(--text-dim)">AI Score: ${r.ai_score}</span>
            </div>
            <div class="rec-prices">
                <div class="rec-price-item">
                    <div class="rec-price-label">ENTRY ZONE</div>
                    <div class="rec-price-val">${r.entry_zone_low} - ${r.entry_zone_high}</div>
                </div>
                <div class="rec-price-item">
                    <div class="rec-price-label">TARGET 1</div>
                    <div class="rec-price-val" style="color:#10b981">${r.target_1}</div>
                </div>
                <div class="rec-price-item">
                    <div class="rec-price-label">STOP LOSS</div>
                    <div class="rec-price-val" style="color:#ef4444">${r.stop_loss}</div>
                </div>
            </div>
            <div class="rec-targets">
                <span class="rec-target">T2: ${r.target_2}</span>
                <span class="rec-target">T3: ${r.target_3}</span>
                <span class="rec-rr">R:R ${r.risk_reward}</span>
            </div>
            <div class="rec-reasons">
                ${r.key_reasons.slice(0,2).map(rea => `<div class="rec-reason">${rea}</div>`).join('')}
                ${r.risk_factors.slice(0,1).map(risk => `<div class="rec-reason rec-risk">${risk}</div>`).join('')}
            </div>
        </div>`;
    }).join('');
}

function renderPatterns(preds) {
    const grid = document.getElementById('patternsGrid');
    if (!grid) return;
    
    // Find predictions that have pattern reasons
    const patternsFound = [];
    for (const p of preds) {
        if (!p.key_reasons) continue;
        const matched = p.key_reasons.filter(r => r.includes('Candlestick Strategy:') || r.includes('Chart Pattern Strategy:'));
        if (matched.length > 0) {
            patternsFound.push({
                symbol: p.display,
                exchange: p.exchange,
                price: p.current_price,
                action: p.action,
                prob: p.direction_probability,
                patterns: matched,
                sector: p.sector,
                news: p.news_sentiment
            });
        }
    }
    
    setText('patternCount', `${patternsFound.length} patterns detected`);
    
    if (patternsFound.length === 0) {
        grid.innerHTML = '<div style="padding:20px;color:var(--text-dim);grid-column:1/-1;text-align:center">No distinct chart patterns detected on the daily timeframe at this moment.</div>';
        return;
    }
    
    grid.innerHTML = patternsFound.map(r => {
        const isBuy = r.action === 'BUY';
        const color = isBuy ? '#10b981' : (r.action === 'SELL SHORT' ? '#ef4444' : '#f59e0b');
        
        return `<div class="rec-card ${isBuy ? 'buy' : 'sell'}" style="border:1px solid ${color}40">
            <div class="rec-header" style="border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:10px;margin-bottom:10px">
                <div>
                    <div class="rec-symbol" style="font-size:16px">${r.symbol} <span style="font-size:10px;color:var(--text-dim);font-weight:400">${r.exchange}</span></div>
                    <div style="font-size:11px;color:${color};font-weight:700;margin-top:4px">${r.action} (Prob: ${r.prob}%)</div>
                </div>
                <div class="rec-grade" style="background:transparent;color:var(--text-primary);font-size:14px;border:1px solid rgba(255,255,255,0.1)">₹${r.price}</div>
            </div>
            <div class="rec-meta" style="margin-bottom:10px">
                <span class="rec-sector">${r.sector}</span>
                <span style="font-size:9px;color:${r.news==='BULLISH'?'#10b981':r.news==='BEARISH'?'#ef4444':'var(--text-dim)'}">News: ${r.news}</span>
            </div>
            <div class="rec-reasons" style="gap:6px">
                ${r.patterns.map(p => {
                    const isBull = p.includes('Bullish') || p.includes('Bottom') || p.includes('Breakout');
                    const isBear = p.includes('Bearish') || p.includes('Top') || p.includes('Breakdown');
                    const pColor = isBull ? '#10b981' : (isBear ? '#ef4444' : 'var(--text-bright)');
                    const bg = isBull ? 'rgba(16,185,129,0.1)' : (isBear ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.05)');
                    const text = p.replace('Candlestick Strategy: ', '').replace('Chart Pattern Strategy: ', '');
                    return `<div class="rec-reason" style="background:${bg};color:${pColor};border-left:2px solid ${pColor};padding:8px 10px;font-size:12px;font-weight:500">${text}</div>`;
                }).join('')}
            </div>
        </div>`;
    }).join('');
}

function renderOutlook(o) {
    setText('outlookDate', o.date);
    setText('outlookNiftyDir', o.nifty_direction);
    setText('outlookNiftyProb', `${o.nifty_probability}% probability`);
    setText('outlookRange', `${o.nifty_range_low} - ${o.nifty_range_high}`);
    setText('outlookSentiment', o.sentiment);
    setText('outlookVix', o.india_vix_outlook);
    setText('outlookRegime', o.regime.replace('_',' ').toUpperCase());
    
    document.getElementById('macroFactors').innerHTML = 
        o.key_risks.map(r => `<div class="factor-item risk">${r}</div>`).join('') +
        o.macro_factors.map(m => `<div class="factor-item macro">${m}</div>`).join('');
        
    document.getElementById('sectorRotation').innerHTML = 
        o.sector_rotation.map(s => `<div class="sector-rot-item">
            <span class="sector-rot-name">${s.sector}</span>
            <span class="sector-rot-score">${s.avg_score} (AI)</span>
        </div>`).join('');
        
    // Full outlook page body
    document.getElementById('outlookFullBody').innerHTML = `
        <div class="outlook-section">
            <div class="outlook-section-title">Nifty 50 Forecast</div>
            <p style="font-size:13px;line-height:1.6;color:var(--text-primary)">
                Market is expected to be <strong>${o.nifty_direction}</strong> tomorrow with a ${o.nifty_probability}% probability.<br>
                Expected Trading Range: <strong>${o.nifty_range_low}</strong> to <strong>${o.nifty_range_high}</strong>.<br>
                Primary Target: <strong>${o.nifty_target}</strong>.
            </p>
        </div>
        <div class="outlook-section">
            <div class="outlook-section-title">Top Actionable Picks</div>
            <div>${o.top_picks.map(p => `<span class="pick-pill">${p}</span>`).join('')}</div>
            <div style="margin-top:10px;font-size:11px;color:var(--text-dim)">Avoid: ${o.avoid_list.join(', ')}</div>
        </div>
        <div class="outlook-section">
            <div class="outlook-section-title">News & Sentiment Summary</div>
            <p style="font-size:12px;color:var(--text-secondary)">${o.news_summary}</p>
        </div>
    `;
    setText('outlookGenTime', 'Generated: ' + o.generated_at);
}

function filterPredictions() {
    const q = document.getElementById('predSearch').value.toLowerCase();
    const tbody = document.getElementById('predictionsBody');
    let html = '';
    let count = 0;
    for(const p of allPredictions) {
        if(q && !p.display.toLowerCase().includes(q)) continue;
        const color = p.action==='BUY'?'#10b981':p.action==='SELL SHORT'?'#ef4444':'#f59e0b';
        html += `<tr>
            <td><strong>${p.display}</strong></td>
            <td><span class="exch-pill ${(p.exchange||'nse').toLowerCase()}">${p.exchange}</span></td>
            <td>${p.current_price}</td>
            <td style="color:${color}">${p.direction}</td>
            <td>${p.direction_probability}%</td>
            <td><strong>${p.confidence_grade}</strong></td>
            <td><span class="signal-pill ${p.action==='BUY'?'buy':p.action.includes('SELL')?'sell':'hold'}">${p.action}</span></td>
            <td>${p.entry_price}</td>
            <td>${p.stop_loss}</td>
            <td>${p.target_1}</td>
            <td>${p.target_2}</td>
            <td style="color:var(--accent-cyan)">${p.risk_reward}</td>
            <td style="color:${p.news_sentiment==='BULLISH'?'#10b981':p.news_sentiment==='BEARISH'?'#ef4444':'#64748b'}">${p.news_sentiment}</td>
            <td>${p.strategy_confirmations}</td>
            <td style="font-size:9px;color:var(--text-dim)">${p.sector.substring(0,12)}</td>
        </tr>`;
        count++;
    }
    tbody.innerHTML = html || '<tr><td colspan="15" style="text-align:center;padding:20px;color:var(--text-dim)">No matches found</td></tr>';
    setText('predCount', `${count} predictions`);
}

function filterNews(type, el) {
    currentNewsFilter = type;
    if(el) {
        el.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        el.classList.add('active');
    }
    const container = document.getElementById('newsFeed');
    let filtered = allNews;
    if(type === 'HIGH') filtered = allNews.filter(n => n.impact === 'HIGH');
    else if(type === 'BULLISH' || type === 'BEARISH') filtered = allNews.filter(n => n.sentiment === type);
    else if(type === 'MACRO') filtered = allNews.filter(n => n.is_macro);
    
    if(!filtered.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-dim)">No news matching filter</div>';
        return;
    }
    
    container.innerHTML = filtered.map(n => {
        const dot = n.sentiment==='BULLISH'?'bullish':n.sentiment==='BEARISH'?'bearish':'neutral';
        const d = new Date(n.published);
        const time = isNaN(d.getTime()) ? n.published.substring(11,16) : d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
        return `<div class="news-item">
            <div class="news-sentiment-dot ${dot}"></div>
            <div class="news-content">
                <div class="news-title"><a href="${n.url}" target="_blank">${n.title}</a></div>
                <div class="news-meta">
                    <span class="news-source">${n.source}</span>
                    <span class="news-time">${time}</span>
                    <span class="news-impact ${n.impact}">${n.impact} IMPACT</span>
                    <div class="news-tags">
                        ${n.affected_symbols.map(s => `<span class="news-tag">${s.replace('.NS','')}</span>`).join('')}
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
}

function updateNewsStats(news) {
    setText('newsSentDetail', `${news.length} articles processed`);
    const highs = news.filter(n => n.impact === 'HIGH').length;
    setText('newsHighImpact', highs);
    const macros = news.filter(n => n.is_macro).length;
    setText('newsMacroCount', macros);
    const sources = new Set(news.map(n=>n.source));
    setText('newsSourceCount', sources.size);
    setText('newsLastUpdate', `Last: ${new Date().toLocaleTimeString()}`);
    
    let score = 0;
    if(news.length) {
        score = news.reduce((acc, n) => acc + n.sentiment_score, 0) / news.length;
    }
    const sentEl = document.getElementById('newsSentScore');
    sentEl.textContent = score > 0.1 ? 'BULLISH' : score < -0.1 ? 'BEARISH' : 'NEUTRAL';
    sentEl.className = 'stat-value ' + (score > 0.1 ? 'positive' : score < -0.1 ? 'negative' : 'neutral');
}

function filterRecs(type, el) {
    currentRecFilter = type;
    el.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    fetch('/api/v4/recommendations').then(r=>r.json()).then(renderRecommendations);
}

// Stubs for other renders (Positions, Trades, Agents, Chart)
function renderPositions(pos) {
    setText('posCount', pos.length);
    const t = document.getElementById('positionsBody');
    if(!pos.length) return t.innerHTML='<tr><td colspan="7" align="center" style="color:var(--text-dim)">No open positions</td></tr>';
    t.innerHTML = pos.map(p => `<tr>
        <td><strong>${p.display}</strong></td>
        <td><span class="exch-pill ${(p.exchange||'nse').toLowerCase()}">${p.exchange}</span></td>
        <td><span class="signal-pill ${p.direction==='LONG'?'buy':'sell'}">${p.direction}</span></td>
        <td>${p.entry_price.toFixed(2)}</td>
        <td>${p.current_price.toFixed(2)}</td>
        <td class="${p.unrealized_pnl>=0?'positive':'negative'}">${p.unrealized_pnl>=0?'+':''}${p.unrealized_pnl.toFixed(0)} (${p.pnl_pct>=0?'+':''}${p.pnl_pct.toFixed(2)}%)</td>
        <td style="font-size:9px;color:var(--text-dim)">${p.strategy_id}</td>
    </tr>`).join('');
}

function renderTrades(trd) {
    setText('historyCount', trd.length);
    const t = document.getElementById('tradesBody');
    if(!trd.length) return t.innerHTML='<tr><td colspan="6" align="center" style="color:var(--text-dim)">No trades yet</td></tr>';
    t.innerHTML = trd.slice(-15).reverse().map(p => `<tr>
        <td><strong>${p.display}</strong></td>
        <td><span class="signal-pill ${p.direction==='LONG'?'buy':'sell'}">${p.direction}</span></td>
        <td class="${p.pnl>=0?'positive':'negative'}">${p.pnl>=0?'+':''}${p.pnl.toFixed(0)}</td>
        <td class="${p.pnl_pct>=0?'positive':'negative'}">${p.pnl_pct>=0?'+':''}${p.pnl_pct.toFixed(2)}%</td>
        <td style="font-size:9px;color:var(--text-dim)">${p.strategy_id}</td>
        <td style="font-size:9px;color:var(--text-dim)">${p.exit_reason}</td>
    </tr>`).join('');
}

function renderAgents(agt) {
    const keys = Object.keys(agt);
    if(!keys.length) return;
    const grid = document.getElementById('agentGrid');
    grid.innerHTML = keys.map(k => {
        const a = agt[k];
        const dir = a.direction||0.5;
        const color = dir>0.6?'#10b981':dir<0.4?'#ef4444':'#f59e0b';
        const cls = dir>0.6?'bullish':dir<0.4?'bearish':'neutral';
        return `<div class="agent-card">
            <div class="agent-name">${k}</div>
            <div class="agent-vals"><span style="color:${color}">${(dir*100).toFixed(0)}%</span><span style="color:var(--text-dim)">c:${(a.confidence*100).toFixed(0)}%</span></div>
            <div class="agent-bar"><div class="agent-bar-fill ${cls}" style="width:${dir*100}%"></div></div>
        </div>`;
    }).join('');
}

function renderSectors(sec) {
    const grid = document.getElementById('sectorGrid');
    const keys = Object.keys(sec);
    setText('sectorCount', keys.length + ' sectors');
    if(!keys.length) return;
    grid.innerHTML = keys.map(k => {
        const arr = sec[k];
        const avg = arr.reduce((acc,v)=>acc+(v.score||50),0)/Math.max(arr.length,1);
        const color = avg>60?'#10b981':avg<40?'#ef4444':'#f59e0b';
        return `<div class="sector-card">
            <div class="sector-name">${k.substring(0,15)}</div>
            <div class="sector-score" style="color:${color}">${avg.toFixed(0)}</div>
            <div class="sector-count">${arr.length} stocks</div>
        </div>`;
    }).join('');
}

function drawChart() {
    const canvas = document.getElementById('equityChart');
    if (!canvas || equityCurve.length < 2) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width; canvas.height = rect.height;
    
    const min = Math.min(...equityCurve)*0.999, max = Math.max(...equityCurve)*1.001;
    const range = max - min || 1;
    const pts = equityCurve.map((v,i) => ({x: canvas.width*i/(equityCurve.length-1), y: canvas.height*(1-(v-min)/range)}));
    
    ctx.beginPath();
    pts.forEach((p,i) => i===0 ? ctx.moveTo(p.x,p.y) : ctx.lineTo(p.x,p.y));
    ctx.strokeStyle = equityCurve[equityCurve.length-1] >= equityCurve[0] ? '#10b981' : '#ef4444';
    ctx.lineWidth = 2; ctx.stroke();
}

function switchRankTab(tab, el) {
    el.parentElement.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    el.classList.add('active');
    const tbody = document.getElementById('rankingBody');
    let f = allRankings;
    if(tab !== 'all') f = allRankings.filter(r => (r.exchange||'').toLowerCase() === tab);
    
    tbody.innerHTML = f.slice(0,10).map((r,i) => {
        const c = r.score>65?'#10b981':r.score<35?'#ef4444':'#f59e0b';
        return `<tr>
            <td>${i+1}</td>
            <td><strong>${r.symbol}</strong></td>
            <td><span class="exch-pill ${(r.exchange||'nse').toLowerCase()}">${r.exchange}</span></td>
            <td style="color:${c};font-weight:700">${r.score}</td>
            <td><span class="signal-pill ${r.action==='BUY'?'buy':r.action==='SELL'?'sell':'hold'}">${r.action}</span></td>
            <td>${r.price}</td>
            <td class="${r.returns_1d>=0?'positive':'negative'}">${r.returns_1d>=0?'+':''}${r.returns_1d}%</td>
            <td>${r.rsi}</td>
            <td style="font-size:9px">${r.sector.substring(0,10)}</td>
        </tr>`;
    }).join('');
}

function setText(id, val) { const e=document.getElementById(id); if(e) e.textContent = val; }
function setClass(id, val) { const e=document.getElementById(id); if(e) { e.classList.remove('positive','negative','neutral'); e.classList.add(val>0?'positive':val<0?'negative':'neutral'); } }
function fmt(v,d=2,s='') { return `${v>=0?'+':''}${v.toFixed(d)}${s}`; }
function formatINR(v) { return `Rs. ${(v/10000000).toFixed(2)} Cr`; }
function formatINRSigned(v) { return `${v>=0?'+':'-'}Rs. ${Math.abs(v/100000).toFixed(2)} L`; }

function renderIntraday(calls) {
    setText('intradayCount', `${calls.length} active calls`);
    const grid = document.getElementById('intradayGrid');
    if(!calls.length) {
        grid.innerHTML = '<div style="padding:20px;color:var(--text-dim)">No active intraday F&O calls currently...</div>';
        return;
    }
    
    grid.innerHTML = calls.map(c => {
        const isLong = c.setup === 'LONG';
        const clr = isLong ? '#10b981' : '#ef4444';
        return `<div class="rec-card ${isLong?'buy':'sell'}">
            <div class="rec-header">
                <div>
                    <div class="rec-symbol">${c.symbol}</div>
                    <div style="font-size:10px;color:${clr};font-weight:700;margin-top:2px">${c.action}</div>
                </div>
                <div class="rec-grade" style="width:auto;padding:0 8px;font-size:11px;background:rgba(59,130,246,0.15);color:#3b82f6">${c.time}</div>
            </div>
            <div class="rec-prices">
                <div class="rec-price-item">
                    <div class="rec-price-label">ENTRY @</div>
                    <div class="rec-price-val">${c.entry}</div>
                </div>
                <div class="rec-price-item">
                    <div class="rec-price-label">TARGET</div>
                    <div class="rec-price-val" style="color:#10b981">${c.target}</div>
                </div>
                <div class="rec-price-item">
                    <div class="rec-price-label">STOP LOSS</div>
                    <div class="rec-price-val" style="color:#ef4444">${c.stop_loss}</div>
                </div>
            </div>
            <div class="rec-reasons">
                <div class="rec-reason">${c.reason}</div>
                <div class="rec-reason">VWAP: ${c.vwap}</div>
                <div class="rec-reason">Conf: ${c.confidence}%</div>
            </div>
        </div>`;
    }).join('');
}

async function searchScreener() {
    const sym = document.getElementById('screenerSearch').value;
    if(!sym) return;
    const res = document.getElementById('screenerResult');
    res.innerHTML = "Fetching from screener.in...";
    try {
        const data = await fetch('/api/v4/screener/'+sym).then(r=>r.json());
        if(!data || !data.symbol) {
            res.innerHTML = "Could not find fundamentals. Try another symbol.";
            return;
        }
        res.innerHTML = `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin-top:15px;color:var(--text-primary)">
            <div class="stat-card" style="margin:0"><div class="stat-label">Stock P/E</div><div class="stat-value neutral">${data.pe_ratio||'--'}</div></div>
            <div class="stat-card" style="margin:0"><div class="stat-label">ROCE</div><div class="stat-value ${data.roce>15?'positive':data.roce<10?'negative':'neutral'}">${data.roce||'--'}%</div></div>
            <div class="stat-card" style="margin:0"><div class="stat-label">ROE</div><div class="stat-value ${data.roe>15?'positive':data.roe<10?'negative':'neutral'}">${data.roe||'--'}%</div></div>
            <div class="stat-card" style="margin:0"><div class="stat-label">Debt to Equity</div><div class="stat-value ${data.debt_to_equity>1?'negative':'positive'}">${data.debt_to_equity||'--'}</div></div>
            <div class="stat-card" style="margin:0"><div class="stat-label">Promoter Holding</div><div class="stat-value neutral">${data.promoter_holding||'--'}%</div></div>
            <div class="stat-card" style="margin:0"><div class="stat-label">AlphaBot Fund. Score</div><div class="stat-value ${data.fundamental_score>60?'positive':'neutral'}">${data.fundamental_score}/100</div></div>
        </div>
        <div style="margin-top:15px;font-size:12px">
            <strong style="color:#10b981">Pros:</strong> ${data.pros ? data.pros.join(' | ') : 'None'}<br><br>
            <strong style="color:#ef4444">Cons:</strong> ${data.cons ? data.cons.join(' | ') : 'None'}
        </div>`;
    } catch(e) { res.innerHTML = "Error fetching data"; }
}

function renderLearningTab(data) {
    if(data.error) return;
    
    setText('lrnOverallAcc', data.overall_accuracy + '%');
    setText('lrnTotalPreds', `Total Predictions Evaluated: ${data.total_predictions}`);
    setText('lrnHits', data.hits);
    setText('lrnMisses', data.misses);
    
    const accEl = document.getElementById('lrnOverallAcc');
    if(accEl) {
        if(data.overall_accuracy >= 60) accEl.style.color = '#10B981';
        else if(data.overall_accuracy <= 40) accEl.style.color = '#EF4444';
        else accEl.style.color = 'var(--accent-cyan)';
    }
    
    const ul = document.getElementById('lrnInsights');
    if(ul && data.insights && data.insights.length > 0) {
        ul.innerHTML = data.insights.map(i => `<li style="margin-bottom:8px">${i}</li>`).join('');
    }
    
    const tbody = document.getElementById('lrnSymbolsBody');
    if(tbody && data.top_symbols && data.top_symbols.length > 0) {
        tbody.innerHTML = data.top_symbols.map(s => {
            const accColor = s.accuracy >= 60 ? '#10B981' : (s.accuracy <= 40 ? '#EF4444' : 'var(--text-bright)');
            const action = s.accuracy < 40 ? '<span style="color:#EF4444">Reduced Volatility Weight</span>' : (s.accuracy > 65 ? '<span style="color:#10B981">Increased Confidence</span>' : 'Monitoring Stability');
            return `
            <tr>
                <td><strong>${s.symbol}</strong></td>
                <td style="color:${accColor};font-weight:bold">${s.accuracy}%</td>
                <td>${s.total}</td>
                <td class="positive">${s.hits}</td>
                <td class="negative">${s.misses}</td>
                <td><span style="font-size:11px;background:var(--bg-darker);padding:4px 8px;border-radius:4px">${action}</span></td>
            </tr>`;
        }).join('');
    }
}

async function startTrading() { await fetch('/api/v4/start', {method:'POST'}); }
async function stopTrading() { await fetch('/api/v4/stop', {method:'POST'}); }
async function emergencyStop() { if(confirm('EMERGENCY STOP?')) await fetch('/api/v4/emergency-stop', {method:'POST'}); }
async function refreshNews() { await fetch('/api/v4/news/refresh', {method:'POST'}); }

document.addEventListener('DOMContentLoaded', async () => {
    connectWebSocket();
    try {
        // Instant sync on refresh to avoid waiting for first WS cycle
        const syncData = await fetch('/api/v4/dashboard/sync').then(r => r.json());
        if(syncData && syncData.type === 'cycle_update') {
            onCycleUpdate(syncData);
        }
    } catch(e) {}
    
    fetchDataAsync(); // Poll the rest immediately too
    setInterval(fetchDataAsync, 15000);
});
window.addEventListener('resize', drawChart);

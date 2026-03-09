from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Live Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #131722; color: white; margin: 0; padding: 20px; }
        
        .header-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; }
        .crypto-selector select { 
            background-color: #2b3139; color: white; border: 1px solid #4a5056; 
            padding: 10px 15px; font-size: 18px; border-radius: 4px; cursor: pointer; outline: none;
        }
        .live-price-container { display: flex; align-items: baseline; gap: 10px; }
        .live-price-label { font-size: 16px; color: #848e9c; }
        #live-price { font-size: 32px; font-weight: bold; font-family: 'Courier New', Courier, monospace; }
        
        .toolbar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center;}
        button { background-color: #2b3139; color: white; border: 1px solid #4a5056; padding: 8px 16px; cursor: pointer; border-radius: 4px; }
        button:hover { background-color: #3b4249; }
        button.active { background-color: #fcd535; color: black; font-weight: bold; }
        
        /* Style spécifique pour le bouton Volume */
        #toggle-volume { background-color: #26a69a; margin-left: auto; font-weight: bold; }
        #toggle-volume.off { background-color: #ef5350; }

        #chart-container { width: 100%; height: 600px; position: relative; }
        #error-log { color: #ff5252; margin-bottom: 15px; font-weight: bold; }
    </style>
</head>
<body>
    
    <div id="error-log"></div>

    <div class="header-container">
        <div class="crypto-selector">
            <select id="symbol-select">
                <option value="BTCUSDT" selected>Bitcoin (BTC/USDT)</option>
                <option value="ETHUSDT">Ethereum (ETH/USDT)</option>
                <option value="SOLUSDT">Solana (SOL/USDT)</option>
                <option value="XRPUSDT">Ripple (XRP/USDT)</option>
                <option value="XAUUSDT">Or (XAU/USDT)</option>
            </select>
        </div>

        <div class="live-price-container">
            <span class="live-price-label">Prix Actuel :</span>
            <span id="live-price">Chargement...</span>
        </div>
    </div>
    
    <div class="toolbar" id="timeframes">
        <button data-interval="1m" class="active">1m</button>
        <button data-interval="3m">3m</button>
        <button data-interval="5m">5m</button>
        <button data-interval="15m">15m</button>
        <button data-interval="30m">30m</button>
        <button data-interval="1h">1H</button>
        <button data-interval="4h">4H</button>
        <button data-interval="1d">1D</button>
        <button data-interval="1w">1W</button>
        
        <!-- Bouton pour activer/désactiver le volume -->
        <button id="toggle-volume">Volume : ON</button>
    </div>
    
    <div id="chart-container"></div>

    <script>
        const errorLog = document.getElementById('error-log');
        const priceElement = document.getElementById('live-price');
        let currentSymbol = 'BTCUSDT';
        let currentInterval = '1m';
        let previousPrice = 0;
        let isVolumeVisible = true;

        function showError(msg) {
            errorLog.innerHTML = `<p>❌ ${msg}</p>`;
            console.error(msg);
        }

        function updatePriceDisplay(newPrice) {
            // Ajustement dynamique des décimales selon la valeur (ex: XRP à 0.5234, BTC à 64000.50)
            const decimals = newPrice < 10 ? 4 : 2;
            priceElement.innerText = "$" + newPrice.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
            
            if (newPrice > previousPrice) priceElement.style.color = '#26a69a';
            else if (newPrice < previousPrice) priceElement.style.color = '#ef5350';
            else priceElement.style.color = 'white';
            
            previousPrice = newPrice;
        }

        try {
            const chartOptions = { 
                layout: { textColor: '#d1d4dc', background: { type: 'solid', color: '#131722' } },
                grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
                timeScale: { timeVisible: true, secondsVisible: false },
                width: document.getElementById('chart-container').clientWidth,
                height: 600,
                // CONFIGURATION DU ZOOM : La molette zoome (au lieu de scroller)
                handleScroll: { mouseWheel: false, pressedMouseMove: true },
                handleScale: { mouseWheel: true, pinch: true }
            };
            
            const chart = LightweightCharts.createChart(document.getElementById('chart-container'), chartOptions);

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                wickUpColor: '#26a69a', wickDownColor: '#ef5350'
            });

            // CRÉATION DE LA SÉRIE DE VOLUME
            const volumeSeries = chart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: '', // Permet au volume de ne pas écraser l'échelle de prix des bougies
                scaleMargins: {
                    top: 0.8, // Le volume prendra les 20% du bas du graphique
                    bottom: 0,
                },
            });

            let currentSocket = null;
            let lastCandleTime = 0;

            async function fetchHistory(symbol, interval) {
                try {
                    const apiSymbol = symbol === 'XAUUSDT' ? 'PAXGUSDT' : symbol;
                    const response = await fetch(`https://api.binance.com/api/v3/klines?symbol=${apiSymbol}&interval=${interval}&limit=1000`);
                    if (!response.ok) throw new Error(`Erreur réseau HTTP ${response.status}`);
                    
                    const data = await response.json();
                    
                    const candlesData = [];
                    const volumesData = [];

                    data.forEach(d => {
                        const time = Math.floor(d[0] / 1000);
                        const open = parseFloat(d[1]);
                        const close = parseFloat(d[4]);
                        const isUp = close >= open;

                        candlesData.push({
                            time: time, open: open, high: parseFloat(d[2]),
                            low: parseFloat(d[3]), close: close
                        });

                        volumesData.push({
                            time: time,
                            value: parseFloat(d[5]), // d[5] est le volume sur Binance
                            color: isUp ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)' // Couleurs transparentes
                        });
                    });
                    
                    candleSeries.setData(candlesData);
                    volumeSeries.setData(volumesData);
                    
                    lastCandleTime = candlesData[candlesData.length - 1].time;
                    updatePriceDisplay(candlesData[candlesData.length - 1].close);
                    errorLog.innerHTML = ""; 
                } catch (error) {
                    showError(`Impossible de charger l'historique : ` + error.message);
                }
            }

            function connectWebSocket(symbol, interval) {
                if (currentSocket) currentSocket.close();
                
                try {
                    const wsSymbol = symbol === 'XAUUSDT' ? 'paxgusdt' : symbol.toLowerCase();
                    currentSocket = new WebSocket(`wss://stream.binance.com:9443/ws/${wsSymbol}@kline_${interval}`);
                    
                    currentSocket.onmessage = (event) => {
                        const k = JSON.parse(event.data).k;
                        const candleTime = Math.floor(k.t / 1000);
                        const closePrice = parseFloat(k.c);
                        const openPrice = parseFloat(k.o);
                        const isUp = closePrice >= openPrice;
                        
                        updatePriceDisplay(closePrice);

                        if (candleTime >= lastCandleTime) {
                            candleSeries.update({
                                time: candleTime, open: openPrice, 
                                high: parseFloat(k.h), low: parseFloat(k.l), close: closePrice
                            });

                            volumeSeries.update({
                                time: candleTime,
                                value: parseFloat(k.v), // Volume en direct
                                color: isUp ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
                            });

                            lastCandleTime = candleTime;
                        }
                    };
                } catch (error) {
                    showError("Erreur WebSocket : " + error.message);
                }
            }

            function loadChart(symbol, interval) {
                if (interval === '1d' || interval === '1w') {
                    chart.applyOptions({ timeScale: { timeVisible: false } });
                } else {
                    chart.applyOptions({ timeScale: { timeVisible: true, secondsVisible: false } });
                }
                fetchHistory(symbol, interval).then(() => connectWebSocket(symbol, interval));
            }

            // Gestion des boutons Timeframes
            document.querySelectorAll('#timeframes button[data-interval]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('#timeframes button[data-interval]').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    currentInterval = e.target.dataset.interval;
                    loadChart(currentSymbol, currentInterval);
                });
            });

            // Gestion du sélecteur de crypto
            document.getElementById('symbol-select').addEventListener('change', (e) => {
                currentSymbol = e.target.value;
                priceElement.innerText = "Chargement...";
                priceElement.style.color = "white";
                loadChart(currentSymbol, currentInterval);
            });

            // Gestion du bouton Volume ON/OFF
            const volumeBtn = document.getElementById('toggle-volume');
            volumeBtn.addEventListener('click', () => {
                isVolumeVisible = !isVolumeVisible;
                volumeSeries.applyOptions({ visible: isVolumeVisible });
                
                if (isVolumeVisible) {
                    volumeBtn.innerText = "Volume : ON";
                    volumeBtn.classList.remove('off');
                } else {
                    volumeBtn.innerText = "Volume : OFF";
                    volumeBtn.classList.add('off');
                }
            });

            loadChart(currentSymbol, currentInterval); 

            new ResizeObserver(entries => {
                if (entries.length > 0) chart.applyOptions({ width: entries[0].contentRect.width });
            }).observe(document.getElementById('chart-container'));

        } catch (globalError) {
            showError("Erreur fatale : " + globalError.message);
        }
    </script>
</body>
</html>



"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True)

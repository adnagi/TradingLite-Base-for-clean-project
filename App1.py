from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Live Chart</title>
    <!-- Utilisation d'une version fixe et stable de Lightweight Charts -->
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background-color: #131722; color: white; margin: 0; padding: 20px; }
        .toolbar { display: flex; gap: 10px; margin-bottom: 20px; }
        button { background-color: #2b3139; color: white; border: 1px solid #4a5056; padding: 8px 16px; cursor: pointer; border-radius: 4px; }
        button:hover { background-color: #3b4249; }
        button.active { background-color: #fcd535; color: black; font-weight: bold; }
        
        /* Conteneur sécurisé */
        #chart-container { width: 100%; height: 600px; position: relative; }
        
        /* Zone d'affichage des erreurs pour comprendre ce qui bloque */
        #error-log { color: #ff5252; margin-bottom: 15px; font-weight: bold; }
    </style>
</head>
<body>
    <h2>Bitcoin (BTC/USDT) - Temps Réel</h2>
    
    <div id="error-log"></div>
    
    <div class="toolbar" id="timeframes">
        <button data-interval="1m" class="active">1m</button>
        <button data-interval="3m">3m</button>
        <button data-interval="5m">5m</button>
        <button data-interval="15m">15m</button>
        <button data-interval="30m">30m</button>
        <button data-interval="1h">1h</button>
    </div>
    
    <div id="chart-container"></div>

    <script>
        const errorLog = document.getElementById('error-log');
        function showError(msg) {
            errorLog.innerHTML += `<p>❌ ${msg}</p>`;
            console.error(msg);
        }

        try {
            // Initialisation avec des dimensions strictes
            const chartOptions = { 
                layout: { textColor: '#d1d4dc', background: { type: 'solid', color: '#131722' } },
                grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
                timeScale: { timeVisible: true, secondsVisible: false },
                width: document.getElementById('chart-container').clientWidth,
                height: 600
            };
            
            const chart = LightweightCharts.createChart(document.getElementById('chart-container'), chartOptions);

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                wickUpColor: '#26a69a', wickDownColor: '#ef5350'
            });

            let currentSocket = null;
            let lastCandleTime = 0;

            async function fetchHistory(interval) {
                try {
                    const response = await fetch(`https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=${interval}&limit=1000`);
                    if (!response.ok) throw new Error(`Erreur réseau Binance HTTP ${response.status}`);
                    
                    const data = await response.json();
                    if (!Array.isArray(data) || data.length === 0) throw new Error("Binance a renvoyé des données vides.");

                    const formattedData = data.map(d => ({
                        time: Math.floor(d[0] / 1000), 
                        open: parseFloat(d[1]), 
                        high: parseFloat(d[2]),
                        low: parseFloat(d[3]), 
                        close: parseFloat(d[4])
                    }));
                    
                    candleSeries.setData(formattedData);
                    
                    // Sauvegarder le dernier timestamp pour éviter les conflits WebSocket
                    lastCandleTime = formattedData[formattedData.length - 1].time;
                    errorLog.innerHTML = ""; // Effacer les erreurs si succès
                } catch (error) {
                    showError("Impossible de charger l'historique : " + error.message);
                }
            }

            function connectWebSocket(interval) {
                if (currentSocket) currentSocket.close();
                
                try {
                    currentSocket = new WebSocket(`wss://stream.binance.com:9443/ws/btcusdt@kline_${interval}`);
                    
                    currentSocket.onmessage = (event) => {
                        const k = JSON.parse(event.data).k;
                        const candleTime = Math.floor(k.t / 1000);
                        
                        // Sécurité : Ne mettre à jour que si le temps est >= à la dernière bougie
                        if (candleTime >= lastCandleTime) {
                            candleSeries.update({
                                time: candleTime,
                                open: parseFloat(k.o), 
                                high: parseFloat(k.h),
                                low: parseFloat(k.l), 
                                close: parseFloat(k.c)
                            });
                            lastCandleTime = candleTime;
                        }
                    };

                    currentSocket.onerror = (err) => showError("Erreur de connexion WebSocket Live.");
                } catch (error) {
                    showError("Erreur lors de l'initialisation du WebSocket : " + error.message);
                }
            }

            function loadTimeframe(interval) {
                fetchHistory(interval).then(() => connectWebSocket(interval));
            }

            // Gestionnaire de clics
            document.querySelectorAll('#timeframes button').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('#timeframes button').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    loadTimeframe(e.target.dataset.interval);
                });
            });

            // Lancement
            loadTimeframe('1m'); 

            // Redimensionnement fluide
            new ResizeObserver(entries => {
                if (entries.length > 0) {
                    chart.applyOptions({ width: entries[0].contentRect.width });
                }
            }).observe(document.getElementById('chart-container'));

        } catch (globalError) {
            showError("Erreur fatale du script : " + globalError.message);
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

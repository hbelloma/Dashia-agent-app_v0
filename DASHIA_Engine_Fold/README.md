# DASHIA engine (port Python)

Port funcional del Pine Script `DASHIA.pine` (Héctor Bello / Two Level Capital,
licencia MPL 2.0) para poder correrlo dentro de la app sin depender de la API
de TradingView.

## Instalación

```bash
pip install pandas numpy matplotlib
python -m dashia_engine.demo
```

Genera `dashia_summary.json`, `dashia_trades.csv` y `dashia_equity_curve.png`.

## Uso básico

```python
from dashia_engine import DashiaConfig, run_dashia, run_backtest, RiskConfig, load_csv

df = load_csv("BTCUSDT_1h.csv")  # columnas: timestamp, open, high, low, close, volume
cfg = DashiaConfig(risk=RiskConfig(plan="WALK", sltp_method="PERCENTAGE"))
signals = run_dashia(df, cfg)
result = run_backtest(signals, cfg.risk)
print(result.summary())
```

## Qué se portó y qué se documenta como supuesto

| Componente | Estado | Nota |
|---|---|---|
| Features normalizados (RSI, Stoch K/D, MFI, RVI, CCI, WaveTrend, ADX) | Fiel | `indicators.py` |
| Distancia Lorentziana + ANN aproximado | Fiel, literal | Incluye la ventana de referencia **fija** (no deslizante) y el filtro `i % 4` tal como está escrito en el pine, no como lo describe el comentario |
| Etiqueta de entrenamiento (`y_train`) | Fiel, con bandera | `invert_labels=True/False` para comparar ambas convenciones contra el backtest real de TradingView |
| Kernel Rational Quadratic / Gaussian | Adaptado | El pine usa `array.from(_src)` sobre un escalar, lo que colapsa la ventana. Aquí se implementó la versión estándar publicada del kernel (ventana de `lookback` barras) |
| Filtros de régimen / ADX / volatilidad / cruce KD | Fiel | `filters.py` |
| Salidas dinámicas (kernel-based) | **No portado aún** | Se implementó solo el modo estricto por conteo de barras (el modo por defecto del script, `useDynamicExits=false`) |
| Planes de riesgo COOK/WALK/HAWK/ALLIN + sizing | Fiel | `risk.py`, misma fórmula `qty = (equity*risk%/100)/(price*SL%/100)` |
| SL/TP porcentual, ATR, trailing | Porcentual y ATR fieles; trailing pendiente | `risk.py` / `backtest.py` |

## Rendimiento

El bucle ANN es `O(n_barras * max_bars_back)` porque replica el algoritmo
línea por línea. Para producción (datos en vivo, historial largo) conviene:
- Vectorizar con NumPy/Numba la función `lorentzian_ann`.
- Cachear el vector de features y recalcular solo la última barra en cada
  tick, en vez de recorrer todo el historial en cada llamada.

## Antes de operar con dinero real

Esto es un port de ingeniería, no una validación de la estrategia. Antes de
conectarlo a una cuenta real: (1) correrlo contra datos históricos reales
(exportados vía ccxt u otra fuente) y comparar los trades contra el
Strategy Tester de TradingView para el mismo rango de fechas, (2) probar en
una cuenta demo/testnet, (3) revisar especialmente la fila "Etiqueta de
entrenamiento" de la tabla de arriba con ambas banderas.

Licencia del algoritmo original: Mozilla Public License 2.0. Autor: Héctor
Bello (Two Level Capital).

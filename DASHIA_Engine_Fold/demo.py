"""
demo.py
=======
Corre el pipeline completo de DASHIA sobre una serie sintética (este
sandbox no tiene salida de red hacia exchanges) y guarda:
  - dashia_equity_curve.png
  - dashia_trades.csv
  - dashia_summary.json

Para usar datos reales: sustituir synthetic_ohlcv() por load_csv() con
un CSV exportado de tu exchange, o por un conector en vivo en producción.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dashia_engine import DashiaConfig, run_dashia, run_backtest, RiskConfig, synthetic_ohlcv

df = synthetic_ohlcv(n_bars=800, start_price=60_000.0, seed=7, freq="1h")

cfg = DashiaConfig(
    neighbors_count=8,
    max_bars_back=250,
    feature_count=10,
    use_kd_cross_filter=True,
    use_kernel_filter=True,
    risk=RiskConfig(plan="ALLIN", risk_capital_pct=100, sltp_method="PERCENTAGE",
                     stop_loss_pct=2.0, take_profit_pct=10.0),
)

signals_df = run_dashia(df, cfg)
result = run_backtest(signals_df, cfg.risk, initial_capital=10_000.0)

summary = result.summary()
print("=== DASHIA · resumen de backtest (datos sintéticos) ===")
for k, v in summary.items():
    print(f"{k:>24}: {v}")

with open("dashia_summary.json", "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

trades_df = None
if result.trades:
    import pandas as pd
    trades_df = pd.DataFrame([{
        "entrada": tr.entry_time, "salida": tr.exit_time, "lado": tr.side,
        "precio_entrada": round(tr.entry_price, 2), "precio_salida": round(tr.exit_price, 2),
        "cantidad": round(tr.qty, 6), "razon_salida": tr.exit_reason,
        "pnl": round(tr.pnl, 2), "pnl_%": round(tr.pnl_pct, 2),
    } for tr in result.trades])
    trades_df.to_csv("dashia_trades.csv", index=False)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                gridspec_kw={"height_ratios": [2, 1]})
ax1.plot(df.index, df["close"], color="#888880", linewidth=0.8, label="Precio (sintético)")
buys = signals_df[signals_df["start_long"]]
sells = signals_df[signals_df["start_short"]]
ax1.scatter(buys.index, buys["close"], marker="^", color="#3B8BD4", s=35, label="Entrada long", zorder=3)
ax1.scatter(sells.index, sells["close"], marker="v", color="#D05538", s=35, label="Entrada short", zorder=3)
ax1.set_ylabel("Precio")
ax1.legend(loc="upper left", fontsize=8)
ax1.set_title("DASHIA sobre serie sintética · señales de entrada")

ax2.plot(result.equity_curve.index, result.equity_curve.values, color="#0F6E56", linewidth=1.2)
ax2.axhline(result.initial_capital, color="#888880", linewidth=0.6, linestyle="--")
ax2.set_ylabel("Equity (USD)")
ax2.set_title(f"Equity curve · retorno {summary['retorno_total_%']}% · {summary['operaciones']} operaciones")

plt.tight_layout()
plt.savefig("dashia_equity_curve.png", dpi=140)
print("\nArchivos generados: dashia_equity_curve.png, dashia_trades.csv, dashia_summary.json")

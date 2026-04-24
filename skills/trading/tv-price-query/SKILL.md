---
name: tv-price-query
description: Query real-time price and candle data using the TradingView adapter infrastructure.
---

# tv-price-query
Query real-time price and candle data using the TradingView adapter infrastructure.

## Trigger
- User asks for current price of a symbol (e.g., "BTC price", "What is ETH doing?")
- User asks for recent market activity or candles.

## Procedure
1. **Environment Check**: Ensure `trading_infra/` is in `PYTHONPATH` and the active `venv` has `backtrader`, `pandas`, and `numpy` installed.
2. **Initialize Store**: Instantiate `TradingViewStore(symbol)` from `trading_infra.adapter`.
3. **Start Socket**: Call `store.start_socket(timeframe=TimeFrame.Minutes, compression=1)` to begin the data stream.
4. **Collect Data**: Poll `store.q_store` for the latest completed candle.
5. **Format Result**: Extract the `close` price and return it to the user in a clean, terminal-friendly format.

## Requirements
- `trading_infra/` directory must exist with `adapter.py`, `ticker.py`, and `test_run.py`.
- A functional `ticker.py` (can be the simulator for testing or a real WebSocket client for live data).

## Pitfalls
- **Simulated vs Real**: Always verify if `ticker.py` is providing live data or just a random walk.
- **Timeout**: If `q_store.get()` times out, the connection/socket is not emitting data; report a connection error.
- **Venv Isolation**: Always execute via the specific virtual environment's python binary to avoid `ModuleNotFoundError`.
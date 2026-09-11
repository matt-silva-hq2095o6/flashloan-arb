# flashloan-arb

Simple CLI tool to watch Uniswap v2 style pools (Uniswap, Sushiswap, etc.) on EVM networks, find cyclic arbitrage paths (2-hop and 3-hop), and calculate optimal input sizes using closed-form equations instead of binary search.

I built this to evaluate whether pool imbalances on Arbitrum and Base cover flashloan fees (e.g. 0.05% on Balancer or 0.09% on Aave) plus L2 gas before spending time writing execution contracts.

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/username/flashloan-arb.git
cd flashloan-arb
pip install .
```

## Usage

Pass an RPC endpoint and a JSON file containing the pool list you want to monitor:

```bash
# Scan a local anvil fork
python -m flashloan_arb scan --rpc http://127.0.0.1:8545 --pools pools.sample.json

# Run single-shot calculation on known reserves
python -m flashloan_arb calc --pair-a 1200000,450 --pair-b 1180000,450 --fee 30
```

Pools JSON format:
```json
[
  {
    "address": "0x...",
    "token0": "0x...",
    "token1": "0x...",
    "fee_bps": 30,
    "dex": "sushiswap"
  }
]
```

## Notes

- Uses Multicall3 for fetching reserves in a single eth_call.
- Math assumes standard constant product xy=k invariant.
- Does not submit bundles or private txs; outputs JSON or rich tables for piping into downstream runners.

<!-- checked: 2026-09-11 -->

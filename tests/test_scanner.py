import pytest
from flashloan_arb.types import Pool, Token
from flashloan_arb.scanner import (
    build_pool_graph,
    find_cycles_from_token,
    filter_viable_routes,
)


WETH = Token("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "WETH", 18)
USDC = Token("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", 6)
DAI = Token("0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI", 18)
WBTC = Token("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "WBTC", 8)
SHIT = Token("0xdead000000000000000000000000000000000001", "SHIT", 18)


@pytest.fixture
def mock_pools():
    return [
        Pool(
            address="0x0001",
            factory="sushiswap",
            token0=WETH,
            token1=USDC,
            reserve0=1000 * 10**18,
            reserve1=2_000_000 * 10**6,
            fee=997,
        ),
        Pool(
            address="0x0002",
            factory="uniswap_v2",
            token0=WETH,
            token1=USDC,
            reserve0=800 * 10**18,
            reserve1=2_000_000 * 10**6,
            fee=997,
        ),
        Pool(
            address="0x0003",
            factory="uniswap_v2",
            token0=USDC,
            token1=DAI,
            reserve0=5_000_000 * 10**6,
            reserve1=5_000_000 * 10**18,
            fee=997,
        ),
        Pool(
            address="0x0004",
            factory="sushiswap",
            token0=DAI,
            token1=WETH,
            reserve0=4_000_000 * 10**18,
            reserve1=1800 * 10**18,
            fee=997,
        ),
        # Dead-end pool with no way back to WETH
        Pool(
            address="0x0005",
            factory="sushiswap",
            token0=WETH,
            token1=SHIT,
            reserve0=10 * 10**18,
            reserve1=10000 * 10**18,
            fee=997,
        ),
        # Zero reserve pool that should be dropped
        Pool(
            address="0x0006",
            factory="uniswap_v2",
            token0=WETH,
            token1=DAI,
            reserve0=0,
            reserve1=0,
            fee=997,
        ),
    ]


def test_build_graph_ignores_empty_pools(mock_pools):
    graph = build_pool_graph(mock_pools, min_reserve_usd=1.0)
    # 0x0006 had 0 reserves, shouldn't appear in edges
    for token_addr, edges in graph.items():
        for edge in edges:
            assert edge.pool.address != "0x0006"


def test_find_cycles_avoids_dead_ends(mock_pools):
    cycles = find_cycles_from_token(mock_pools, start_token=WETH, max_hops=3)
    
    # None of the cycles should contain the dead-end token
    for c in cycles:
        for hop in c.hops:
            assert hop.pool.token0.address != SHIT.address
            assert hop.pool.token1.address != SHIT.address


def test_filter_viable_routes(mock_pools):
    cycles = find_cycles_from_token(mock_pools, start_token=WETH, max_hops=3)
    viable = filter_viable_routes(cycles, min_profit_wei=10**15)  # min 0.001 ETH profit
    
    assert len(viable) > 0
    for route in viable:
        assert route.expected_profit >= 10**15
        assert route.optimal_dx > 0

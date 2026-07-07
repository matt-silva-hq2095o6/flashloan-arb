import pytest
from flashloan_arb.math import (
    get_amount_out,
    calc_optimal_dx_2hop,
    simulate_cycle,
    calc_optimal_dx_ternary
)


def brute_force_optimal_dx(r1_in, r1_out, r2_in, r2_out, fee1=997, fee2=997, step_pct=0.001):
    best_dx = 0
    best_profit = 0
    max_scan = int(r1_in * 0.5)
    step = max(1, int(max_scan * step_pct))
    
    for dx in range(1, max_scan, step):
        out1 = get_amount_out(dx, r1_in, r1_out, fee1)
        if out1 <= 0 or out1 >= r2_in:
            continue
        out2 = get_amount_out(out1, r2_in, r2_out, fee2)
        profit = out2 - dx
        if profit > best_profit:
            best_profit = profit
            best_dx = dx
            
    return best_dx, best_profit


def test_get_amount_out_standard_uniswap_v2():
    expected = 1974
    res = get_amount_out(1000, 100_000, 200_000)
    assert res == expected


def test_get_amount_out_zero_cases():
    assert get_amount_out(0, 100_000, 200_000) == 0
    assert get_amount_out(100, 0, 200_000) == 0
    assert get_amount_out(100, 100_000, 0) == 0


def test_optimal_dx_matches_numerical_stepping():
    r1_weth, r1_usdc = 800 * 10**18, 2_000_000 * 10**6
    r2_usdc, r2_weth = 2_000_000 * 10**6, 1000 * 10**18
    
    dx_analytical = calc_optimal_dx_2hop(r1_weth, r1_usdc, r2_usdc, r2_weth)
    assert dx_analytical > 0
    
    dx_brute, profit_brute = brute_force_optimal_dx(r1_weth, r1_usdc, r2_usdc, r2_weth, step_pct=0.0005)
    
    out1 = get_amount_out(dx_analytical, r1_weth, r1_usdc)
    out2 = get_amount_out(out1, r2_usdc, r2_weth)
    profit_analytical = out2 - dx_analytical
    
    assert profit_analytical >= profit_brute
    diff_ratio = abs(dx_analytical - dx_brute) / dx_analytical
    assert diff_ratio < 0.01


def test_no_arbitrage_returns_zero():
    r1_a, r1_b = 1000 * 10**18, 2_000_000 * 10**6
    r2_b, r2_a = 2_000_000 * 10**6, 1000 * 10**18
    
    dx = calc_optimal_dx_2hop(r1_a, r1_b, r2_b, r2_a)
    assert dx == 0


def test_simulate_cycle_triangle():
    # Pool 1: WETH -> USDC (Sushi)
    # Pool 2: USDC -> DAI (UniV2)
    # Pool 3: DAI -> WETH (Pancake)
    hops = [
        (500 * 10**18, 1_500_000 * 10**6, 997),
        (2_000_000 * 10**6, 2_005_000 * 10**18, 997),
        (3_000_000 * 10**18, 1050 * 10**18, 997),
    ]
    
    dx_test = 10 * 10**18
    net_out = simulate_cycle(dx_test, hops)
    assert net_out > 0


def test_calc_optimal_dx_ternary_matches_simulate():
    hops = [
        (500 * 10**18, 1_500_000 * 10**6, 997),
        (2_000_000 * 10**6, 2_005_000 * 10**18, 997),
        (3_000_000 * 10**18, 1050 * 10**18, 997),
    ]
    
    # Max bound is 30% of first hop reserve
    best_dx = calc_optimal_dx_ternary(hops, max_borrow=150 * 10**18)
    assert best_dx > 0
    
    best_profit = simulate_cycle(best_dx, hops) - best_dx
    # Slight shifts left and right should have lower profit
    shift = best_dx // 100
    if shift > 0:
        profit_left = simulate_cycle(best_dx - shift, hops) - (best_dx - shift)
        profit_right = simulate_cycle(best_dx + shift, hops) - (best_dx + shift)
        assert best_profit >= profit_left
        assert best_profit >= profit_right

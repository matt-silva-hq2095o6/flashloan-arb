import math
from typing import Optional, Tuple

# TODO: allow custom fee_num/fee_den per pair instead of assuming uniform 0.3%


def get_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    fee_num: int = 997,
    fee_den: int = 1000,
) -> int:
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    amount_in_with_fee = amount_in * fee_num
    numerator = amount_in_with_fee * reserve_out
    denominator = (reserve_in * fee_den) + amount_in_with_fee
    return numerator // denominator


def get_amount_in(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
    fee_num: int = 997,
    fee_den: int = 1000,
) -> int:
    if amount_out <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    if amount_out >= reserve_out:
        return 0
    numerator = reserve_in * amount_out * fee_den
    denominator = (reserve_out - amount_out) * fee_num
    return (numerator // denominator) + 1


def compute_optimal_2hop(
    r1_in: int,
    r1_out: int,
    r2_in: int,
    r2_out: int,
    fee_num: int = 997,
    fee_den: int = 1000,
) -> Tuple[int, int]:
    """Calculates optimal input amount and expected net profit for a 2-hop arb."""
    if r1_in <= 0 or r1_out <= 0 or r2_in <= 0 or r2_out <= 0:
        return 0, 0

    gamma1 = fee_num / fee_den
    gamma2 = fee_num / fee_den

    radicand = gamma1 * gamma2 * float(r1_in) * float(r1_out) * float(r2_in) * float(r2_out)
    if radicand <= 0:
        return 0, 0

    numerator_sqrt = math.sqrt(radicand)
    numerator = numerator_sqrt - (float(r1_in) * float(r2_in))
    denominator = (gamma1 * float(r2_in)) + (gamma1 * gamma2 * float(r1_out))

    if numerator <= 0 or denominator <= 0:
        return 0, 0

    optimal_in = int(numerator / denominator)
    if optimal_in <= 0:
        return 0, 0

    # print(f"debug: optimal_in={optimal_in} num={numerator} den={denominator}")
    out1 = get_amount_out(optimal_in, r1_in, r1_out, fee_num, fee_den)
    out2 = get_amount_out(out1, r2_in, r2_out, fee_num, fee_den)
    profit = out2 - optimal_in

    if profit <= 0:
        return 0, 0

    return optimal_in, profit


def virtual_reserves_2hop(
    r1_in: int,
    r1_out: int,
    r2_in: int,
    r2_out: int,
    fee_num: int = 997,
    fee_den: int = 1000,
) -> Tuple[int, int]:
    # Collapses two pairs into an equivalent virtual pair (tokenA -> tokenC)
    # based on constant product invariant composition with fee.
    gamma = fee_num / fee_den
    r_prime_in = (float(r1_in) * float(r2_in)) / (float(r2_in) + gamma * float(r1_out))
    r_prime_out = (gamma * float(r1_out) * float(r2_out)) / (float(r2_in) + gamma * float(r1_out))
    return int(r_prime_in), int(r_prime_out)


def compute_optimal_3hop(
    r1_in: int,
    r1_out: int,
    r2_in: int,
    r2_out: int,
    r3_in: int,
    r3_out: int,
    fee_num: int = 997,
    fee_den: int = 1000,
) -> Tuple[int, int]:
    # Reduce first two hops to a single virtual pair, then solve as 2-hop against pool 3
    v_in, v_out = virtual_reserves_2hop(r1_in, r1_out, r2_in, r2_out, fee_num, fee_den)
    if v_in <= 0 or v_out <= 0:
        return 0, 0

    optimal_in, _ = compute_optimal_2hop(v_in, v_out, r3_in, r3_out, fee_num, fee_den)
    if optimal_in <= 0:
        return 0, 0

    # Walk forward with integer math to get the exact profit
    out1 = get_amount_out(optimal_in, r1_in, r1_out, fee_num, fee_den)
    out2 = get_amount_out(out1, r2_in, r2_out, fee_num, fee_den)
    out3 = get_amount_out(out2, r3_in, r3_out, fee_num, fee_den)
    profit = out3 - optimal_in

    if profit <= 0:
        return 0, 0

    return optimal_in, profit

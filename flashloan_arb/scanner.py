from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from flashloan_arb.math import calculate_optimal_input, simulate_cycle_profit
from flashloan_arb.types import ArbitrageOpportunity, Pair, PoolReserve


def build_token_graph(pairs: List[Pair]) -> Dict[str, List[Pair]]:
    graph = defaultdict(list)
    for p in pairs:
        graph[p.token0.lower()].append(p)
        graph[p.token1.lower()].append(p)
    return graph


def _cycle_signature(cycle: List[Tuple[Pair, str, str]]) -> str:
    # Canonical representation so we don't evaluate the same route twice
    return "->".join(f"{p.address.lower()}:{tin}:{tout}" for p, tin, tout in cycle)


class CycleScanner:
    """Finds and evaluates closed token cycles across pair reserves."""

    def __init__(self, pairs: List[Pair], max_hops: int = 3):
        self.pairs = pairs
        self.max_hops = max_hops
        self.graph = build_token_graph(pairs)
        self._cycle_cache: Dict[str, List[List[Tuple[Pair, str, str]]]] = {}

    def find_all_cycles(self, base_token: str) -> List[List[Tuple[Pair, str, str]]]:
        target = base_token.lower()
        if target in self._cycle_cache:
            return self._cycle_cache[target]

        cycles = []
        seen_sigs: Set[str] = set()
        visited_pairs: Set[str] = set()

        def dfs(current_token: str, path: List[Tuple[Pair, str, str]]):
            if len(path) > self.max_hops:
                return

            if len(path) >= 2 and current_token == target:
                sig = _cycle_signature(path)
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    cycles.append(list(path))
                return

            for pair in self.graph.get(current_token, []):
                if pair.address.lower() in visited_pairs:
                    continue

                # pairs can have non-standard token casing from different factory sources
                t0, t1 = pair.token0.lower(), pair.token1.lower()
                out_token = t1 if t0 == current_token else t0
                
                visited_pairs.add(pair.address.lower())
                path.append((pair, current_token, out_token))
                dfs(out_token, path)
                path.pop()
                visited_pairs.remove(pair.address.lower())

        dfs(target, [])
        # TODO: 4-hop cycles are mathematically solvable via quadratic approx but rarely beat gas
        self._cycle_cache[target] = cycles
        return cycles

    def scan(
        self,
        base_token: str,
        reserves_map: Dict[str, PoolReserve],
        min_profit: int = 0,
    ) -> List[ArbitrageOpportunity]:
        cycles = self.find_all_cycles(base_token)
        opportunities = []

        for cycle_steps in cycles:
            step_reserves = []
            valid = True
            for pair, token_in, token_out in cycle_steps:
                res = reserves_map.get(pair.address.lower())
                if not res or res.reserve0 <= 0 or res.reserve1 <= 0:
                    valid = False
                    break
                step_reserves.append((res, token_in, token_out, pair.fee_bps))

            if not valid:
                continue

            # print(f"DEBUG: cycle candidate {[s[1] for s in cycle_steps]} with {len(step_reserves)} hops")
            opt_in = calculate_optimal_input(step_reserves)
            if opt_in <= 0:
                continue

            profit = simulate_cycle_profit(step_reserves, opt_in)
            if profit > min_profit:
                opportunities.append(
                    ArbitrageOpportunity(
                        base_token=base_token,
                        steps=cycle_steps,
                        optimal_input=opt_in,
                        expected_profit=profit,
                    )
                )

        opportunities.sort(key=lambda x: x.expected_profit, reverse=True)
        return opportunities

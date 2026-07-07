from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Token:
    """EVM ERC-20 token representation."""
    address: str
    symbol: str
    decimals: int = 18

    def __post_init__(self):
        object.__setattr__(self, "address", self.address.lower())


@dataclass
class Pool:
    address: str
    token0: Token
    token1: Token
    reserve0: int
    reserve1: int
    fee_num: int = 997
    fee_den: int = 1000
    factory: str = "uniswap_v2"
    block_number: Optional[int] = None

    def __post_init__(self):
        self.address = self.address.lower()

    @property
    def is_empty(self) -> bool:
        return self.reserve0 == 0 or self.reserve1 == 0

    def get_reserves(self, token_in: Token) -> tuple[int, int]:
        if token_in.address == self.token0.address:
            return self.reserve0, self.reserve1
        elif token_in.address == self.token1.address:
            return self.reserve1, self.reserve0
        raise ValueError(f"token {token_in.symbol} ({token_in.address}) not in pool {self.address}")

    def other_token(self, token: Token) -> Token:
        if token.address == self.token0.address:
            return self.token1
        elif token.address == self.token1.address:
            return self.token0
        raise ValueError(f"token {token.symbol} not in pool {self.address}")


@dataclass
class Hop:
    pool: Pool
    token_in: Token
    token_out: Token


@dataclass
class ArbOpportunity:
    hops: list[Hop]
    borrow_token: Token
    optimal_borrow: int
    expected_output: int
    profit: int
    # print(f"DEBUG: profit={profit} borrow={optimal_borrow}")
    # FIXME: fees vary if using balancer vs aave flashloans, hardcoded 0 bps in math for now
    roi_bps: int = 0
    block_number: Optional[int] = None

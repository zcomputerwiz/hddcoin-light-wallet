from dataclasses import dataclass
from typing import List, Optional

from src.types.hashable.coin import Coin
from src.types.sized_bytes import bytes32
from src.util.ints import uint128, uint32, uint64
from src.util.streamable import Streamable, streamable


@dataclass(frozen=True)
@streamable
class BlockRecord(Streamable):
    """
    These are values that are stored in the wallet database, corresponding to infomation
    that the wallet cares about in each block
    """

    header_hash: bytes32
    prev_header_hash: bytes32
    height: uint32
    weight: uint128
    additions: List[Coin]
    removals: List[bytes32]
    timestamp: Optional[uint64]
    total_iters: Optional[uint64]
    new_challenge_hash: Optional[bytes32]

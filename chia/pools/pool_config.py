from dataclasses import dataclass
from pathlib import Path
from typing import List

from blspy import G1Element, G2Element

from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.byte_types import hexstr_to_bytes
from chia.util.config import load_config
from chia.util.ints import uint64
from chia.util.streamable import Streamable, streamable

"""
Config example
This is what goes into the user's config file, to communicate between the wallet and the farmer processes.
pool_list:
  - authentication_key_info_signature: 8fa411d3164d6d4fc1a5985ea474a853304fec99b93300e12e3b3e8fc16dea8834804eb3dfcee7181a59cd4e969ada0e119d7c8cc94f5c912280dc4cfdbadd9076b6393b135e35b182bcd4e13bf9216877a6033dd9f89c249981e83908c5a926
    authentication_public_key: 970e181ae45435ae696508a78012dc80548c334cf29676ea6ade7049eb9d2b9579cc30cb44c3fd68d35a250cfbc69e29
    authentication_public_key_timestamp: 1621854388
    owner_public_key: 84c3fcf9d5581c1ddc702cb0f3b4a06043303b334dd993ab42b2c320ebfa98e5ce558448615b3f69638ba92cf7f43da5
    target_signature: 95ae82302134489d68cf0890356fc2d360c3bda9c9f15a3111a6a776df073a2fc6194896f3196a10fba18bb9de8e4fae0caf08e49fe32786d35fe0538daf0ceb6f7ace9477440b9978589bcaa28690dded6e5a296b47bffe2db97c1c28c9d13c
    pool_payout_instructions: c2b08e41d766da4116e388357ed957d04ad754623a915f3fd65188a8746cf3e8
    pool_url: localhost
    singleton_genesis: ae4ef3b9bfe68949691281a015a9c16630fc8f66d48c19ca548fb80768791afa
    target_puzzle_hash: 344587cf06a39db471d2cc027504e8688a0a67cce961253500c956c73603fd58
"""  # noqa


@dataclass(frozen=True)
@streamable
class PoolWalletConfig(Streamable):
    pool_url: str
    pool_payout_instructions: str
    target_puzzle_hash: bytes32
    launcher_id: bytes32
    owner_public_key: G1Element
    authentication_public_key: G1Element
    authentication_public_key_timestamp: uint64
    authentication_key_info_signature: G2Element


def load_pool_config(root_path: Path) -> List[PoolWalletConfig]:
    config = load_config(root_path, "config.yaml")
    ret_list: List[PoolWalletConfig] = []
    if "pool_list" in config["pool"]:
        for pool_config_dict in config["pool"]["pool_list"]:
            pool_config = PoolWalletConfig(
                pool_config_dict["pool_url"],
                pool_config_dict["pool_payout_instructions"],
                hexstr_to_bytes(pool_config_dict["target_puzzle_hash"]),
                hexstr_to_bytes(pool_config_dict["launcher_id"]),
                G1Element.from_bytes(hexstr_to_bytes(pool_config_dict["owner_public_key"])),
                G1Element.from_bytes(hexstr_to_bytes(pool_config_dict["authentication_public_key"])),
                pool_config_dict["authentication_public_key_timestamp"],
                G2Element.from_bytes(hexstr_to_bytes(pool_config_dict["authentication_key_info_signature"])),
            )
            ret_list.append(pool_config)
    return ret_list
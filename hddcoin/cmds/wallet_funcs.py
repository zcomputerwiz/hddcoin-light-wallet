import asyncio
import sys
import time
from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional, Tuple, Dict

import aiohttp

from hddcoin.cmds.units import units
from hddcoin.rpc.wallet_rpc_client import WalletRpcClient
from hddcoin.server.start_wallet import SERVICE_NAME
from hddcoin.util.bech32m import encode_puzzle_hash
from hddcoin.util.byte_types import hexstr_to_bytes
from hddcoin.util.config import load_config
from hddcoin.util.default_root import DEFAULT_ROOT_PATH
from hddcoin.util.ints import uint16, uint64
from hddcoin.wallet.transaction_record import TransactionRecord
from hddcoin.wallet.util.wallet_types import WalletType


def print_transaction(tx: TransactionRecord, verbose: bool, name) -> None:
    if verbose:
        print(tx)
    else:
        hddcoin_amount = Decimal(int(tx.amount)) / units["hddcoin"]
        to_address = encode_puzzle_hash(tx.to_puzzle_hash, name)
        print(f"Transaction {tx.name}")
        print(f"Status: {'Confirmed' if tx.confirmed else ('In mempool' if tx.is_in_mempool() else 'Pending')}")
        print(f"Amount {'sent' if tx.sent else 'received'}: {hddcoin_amount} {name}")
        print(f"To address: {to_address}")
        print("Created at:", datetime.fromtimestamp(tx.created_at_time).strftime("%Y-%m-%d %H:%M:%S"))
        memos_dict = tx.get_memos()
        if len(memos_dict) > 0:
            print("Memos:")
            for coin_id, memos in memos_dict.items():
                print(coin_id)
                for memo in memos:
                    try:
                        decoded = memo.decode("utf-8")
                        print(f"   - {decoded}")
                    except Exception:
                        print(f"   - {memo.hex()}")
        print("")


async def get_transaction(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    wallet_id = args["id"]
    transaction_id = hexstr_to_bytes(args["tx_id"])
    config = load_config(DEFAULT_ROOT_PATH, "config.yaml", SERVICE_NAME)
    name = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"]
    tx: TransactionRecord = await wallet_client.get_transaction(wallet_id, transaction_id=transaction_id)
    print_transaction(tx, verbose=(args["verbose"] > 0), name=name)


async def get_transactions(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    wallet_id = args["id"]
    paginate = args["paginate"]
    if paginate is None:
        paginate = sys.stdout.isatty()
    txs: List[TransactionRecord] = await wallet_client.get_transactions(wallet_id)
    config = load_config(DEFAULT_ROOT_PATH, "config.yaml", SERVICE_NAME)
    name = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"]
    if len(txs) == 0:
        print("There are no transactions to this address")

    offset = args["offset"]
    num_per_screen = 5 if paginate else len(txs)
    for i in range(offset, len(txs), num_per_screen):
        for j in range(0, num_per_screen):
            if i + j >= len(txs):
                break
            print_transaction(txs[i + j], verbose=(args["verbose"] > 0), name=name)
        if i + num_per_screen >= len(txs):
            return None
        print("Press q to quit, or c to continue")
        while True:
            entered_key = sys.stdin.read(1)
            if entered_key == "q":
                return None
            elif entered_key == "c":
                break


def check_unusual_transaction(amount: Decimal, fee: Decimal):
    return fee >= amount


async def send(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:

    wallet_id = args["id"]
    amount = Decimal(args["amount"])
    fee = Decimal(args["fee"])
    address = args["address"]
    override = args["override"]
    memo = args["memo"]
    if memo is None:
        memos = None
    else:
        memos = [memo]

    if not override and check_unusual_transaction(amount, fee):
        print(
            f"A transaction of amount {amount} and fee {fee} is unusual.\n"
            f"Pass in --override if you are sure you mean to do this."
        )
        return

    summaries_response = await wallet_client.get_wallets()
    final_amount: Optional[uint64] = None
    final_fee = uint64(int(fee * units["hddcoin"]))
    for summary in summaries_response:
        if int(wallet_id) == int(summary["id"]):
            typ: WalletType = WalletType(int(summary["type"]))
            if typ == WalletType.STANDARD_WALLET:
                final_amount = uint64(int(amount * units["hddcoin"]))
                print("Submitting transaction...")
                res = await wallet_client.send_transaction(wallet_id, final_amount, address, final_fee, memos)
                break
            elif typ == WalletType.COLOURED_COIN:
                final_amount = uint64(int(amount * units["colouredcoin"]))
                print("Submitting transaction...")
                res = await wallet_client.cat_spend(wallet_id, final_amount, address, final_fee, memos)
                break
            else:
                print("Only standard wallet and CAT wallets are supported")
                return
    if final_amount is None:
        print(f"Wallet id: {wallet_id} not found.")
        return
    tx_id = res.name
    start = time.time()
    while time.time() - start < 10:
        await asyncio.sleep(0.1)
        tx = await wallet_client.get_transaction(wallet_id, tx_id)
        if len(tx.sent_to) > 0:
            print(f"Transaction submitted to nodes: {tx.sent_to}")
            print(f"Do hddcoin wallet get_transaction -f {fingerprint} -tx 0x{tx_id} to get status")
            return None

    print("Transaction not yet submitted to nodes")
    print(f"Do 'hddcoin wallet get_transaction -f {fingerprint} -tx 0x{tx_id}' to get status")


async def get_address(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    wallet_id = args["id"]
    res = await wallet_client.get_next_address(wallet_id, False)
    print(res)


async def delete_unconfirmed_transactions(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    wallet_id = args["id"]
    await wallet_client.delete_unconfirmed_transactions(wallet_id)
    print(f"Successfully deleted all unconfirmed transactions for wallet id {wallet_id} on key {fingerprint}")


async def add_token(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    asset_id = args["asset_id"]
    token_name = args["token_name"]
    try:
        asset_id_bytes: bytes = hexstr_to_bytes(asset_id)
        response = await wallet_client.create_wallet_for_existing_cat(asset_id_bytes)
        wallet_id = response["wallet_id"]
        await wallet_client.set_cat_name(wallet_id, token_name)
        print(f"Successfully added {token_name} with wallet id {wallet_id} on key {fingerprint}")
    except ValueError as e:
        if "fromhex()" in str(e):
            print(f"{asset_id} is not a valid Asset ID")
        else:
            raise e


def wallet_coin_unit(typ: WalletType, address_prefix: str) -> Tuple[str, int]:
    if typ == WalletType.COLOURED_COIN:
        return "", units["colouredcoin"]
    if typ in [WalletType.STANDARD_WALLET, WalletType.POOLING_WALLET, WalletType.MULTI_SIG, WalletType.RATE_LIMITED]:
        return address_prefix, units["hddcoin"]
    return "", units["byte"]


def print_balance(amount: int, scale: int, address_prefix: str) -> str:
    ret = f"{amount/scale} {address_prefix} "
    if scale > 1:
        ret += f"({amount} byte)"
    return ret


async def print_balances(args: dict, wallet_client: WalletRpcClient, fingerprint: int) -> None:
    summaries_response = await wallet_client.get_wallets()
    config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
    address_prefix = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"]

    print(f"Wallet height: {await wallet_client.get_height_info()}")
    if await wallet_client.get_sync_status():
        print("Sync status: Syncing...")
    else:
        print(f"Sync status: {'Synced' if (await wallet_client.get_synced()) else 'Not synced'}")
    print(f"Balances, fingerprint: {fingerprint}")
    for summary in summaries_response:
        wallet_id = summary["id"]
        balances = await wallet_client.get_wallet_balance(wallet_id)
        typ = WalletType(int(summary["type"]))
        address_prefix, scale = wallet_coin_unit(typ, address_prefix)
        if typ == WalletType.COLOURED_COIN:
            asset_id = await wallet_client.get_cat_colour(wallet_id)
            asset_id_str = f"(Asset ID: {asset_id.hex()})"
        else:
            asset_id_str = ""
        print(f"Wallet ID {wallet_id} type {typ.name} {summary['name']} {asset_id_str}")
        print(f"   -Total Balance: {print_balance(balances['confirmed_wallet_balance'], scale, address_prefix)}")
        print(
            f"   -Pending Total Balance: {print_balance(balances['unconfirmed_wallet_balance'], scale, address_prefix)}"
        )
        print(f"   -Spendable: {print_balance(balances['spendable_balance'], scale, address_prefix)}")


async def get_wallet(wallet_client: WalletRpcClient, fingerprint: int = None) -> Optional[Tuple[WalletRpcClient, int]]:
    if fingerprint is not None:
        fingerprints = [fingerprint]
    else:
        fingerprints = await wallet_client.get_public_keys()
    if len(fingerprints) == 0:
        print("No keys loaded. Run 'hddcoin keys generate' or import a key")
        return None
    if len(fingerprints) == 1:
        fingerprint = fingerprints[0]
    if fingerprint is not None:
        log_in_response = await wallet_client.log_in(fingerprint)
    else:
        print("Choose wallet key:")
        for i, fp in enumerate(fingerprints):
            print(f"{i+1}) {fp}")
        val = None
        while val is None:
            val = input("Enter a number to pick or q to quit: ")
            if val == "q":
                return None
            if not val.isdigit():
                val = None
            else:
                index = int(val) - 1
                if index >= len(fingerprints):
                    print("Invalid value")
                    val = None
                    continue
                else:
                    fingerprint = fingerprints[index]
        assert fingerprint is not None
        log_in_response = await wallet_client.log_in(fingerprint)

    if log_in_response["success"] is False:
        if log_in_response["error"] == "not_initialized":
            use_cloud = True
            if "backup_path" in log_in_response:
                path = log_in_response["backup_path"]
                print(f"Backup file from backup.hddcoin.org downloaded and written to: {path}")
                val = input("Do you want to use this file to restore from backup? (Y/N) ")
                if val.lower() == "y":
                    log_in_response = await wallet_client.log_in_and_restore(fingerprint, path)
                else:
                    use_cloud = False

            if "backup_path" not in log_in_response or use_cloud is False:
                if use_cloud is True:
                    val = input(
                        "No online backup file found,\n Press S to skip restore from backup"
                        "\n Press F to use your own backup file: "
                    )
                else:
                    val = input(
                        "Cloud backup declined,\n Press S to skip restore from backup"
                        "\n Press F to use your own backup file: "
                    )

                if val.lower() == "s":
                    log_in_response = await wallet_client.log_in_and_skip(fingerprint)
                elif val.lower() == "f":
                    val = input("Please provide the full path to your backup file: ")
                    log_in_response = await wallet_client.log_in_and_restore(fingerprint, val)

    if "success" not in log_in_response or log_in_response["success"] is False:
        if "error" in log_in_response:
            error = log_in_response["error"]
            print(f"Error: {log_in_response[error]}")
        return None
    return wallet_client, fingerprint


async def execute_with_wallet(
    wallet_rpc_port: Optional[int], fingerprint: int, extra_params: Dict, function: Callable
) -> None:
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if wallet_rpc_port is None:
            wallet_rpc_port = config["wallet"]["rpc_port"]
        wallet_client = await WalletRpcClient.create(self_hostname, uint16(wallet_rpc_port), DEFAULT_ROOT_PATH, config)
        wallet_client_f = await get_wallet(wallet_client, fingerprint=fingerprint)
        if wallet_client_f is None:
            wallet_client.close()
            await wallet_client.await_closed()
            return None
        wallet_client, fingerprint = wallet_client_f
        await function(extra_params, wallet_client, fingerprint)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            print(
                f"Connection error. Check if the wallet is running at {wallet_rpc_port}. "
                "You can run the wallet via:\n\thddcoin start wallet"
            )
        else:
            print(f"Exception from 'wallet' {e}")
    wallet_client.close()
    await wallet_client.await_closed()
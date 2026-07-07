from typing import Dict, List, Tuple
import httpx

# Multicall3 is deployed at this identical address on almost every chain
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"
GET_RESERVES_CALLDATA = "0902f1ac"


def _encode_try_aggregate(calls: List[Tuple[str, str]], require_success: bool = False) -> str:
    # tryAggregate(bool requireSuccess, (address target, bytes callData)[] calls)
    # selector 0xbce38ced
    call_count = len(calls)
    parts = [
        "bce38ced",
        f"{1 if require_success else 0:064x}",
        f"{64:064x}",  # pointer to array starts after bool and offset itself
        f"{call_count:064x}",
    ]

    # array offset pointers
    running_offset = call_count * 32
    for _ in calls:
        parts.append(f"{running_offset:064x}")
        running_offset += 64 + 32 + 32  # target (32) + callData offset (32) + len (32) + 32-padded calldata

    for target, cdata in calls:
        clean_target = target.lower().removeprefix("0x")
        clean_data = cdata.removeprefix("0x")
        byte_len = len(clean_data) // 2
        padded_data = clean_data.ljust((byte_len + 31) // 32 * 64, "0")

        parts.append(f"{clean_target:0>64}")
        parts.append(f"{64:064x}")  # offset to bytes
        parts.append(f"{byte_len:064x}")
        parts.append(padded_data)

    return "0x" + "".join(parts)


def decode_reserves_result(data_hex: str) -> Tuple[int, int, int]:
    clean = data_hex.removeprefix("0x")
    if len(clean) < 192:
        return 0, 0, 0
    try:
        # uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast
        r0 = int(clean[0:64], 16)
        r1 = int(clean[64:128], 16)
        ts = int(clean[128:192], 16)
        return r0, r1, ts
    except ValueError:
        return 0, 0, 0


def _chunk_list(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def fetch_reserves_batch(
    rpc_url: str,
    pair_addresses: List[str],
    multicall_addr: str = MULTICALL3_ADDRESS,
    chunk_size: int = 400,
    client: httpx.Client = None,
) -> Dict[str, Tuple[int, int]]:
    """Queries getReserves() for a list of UniswapV2 pairs via Multicall3."""
    if not pair_addresses:
        return {}

    out: Dict[str, Tuple[int, int]] = {}
    close_client = False
    if client is None:
        client = httpx.Client(timeout=15.0)
        close_client = True

    try:
        for chunk in _chunk_list(pair_addresses, chunk_size):
            calls = [(addr, GET_RESERVES_CALLDATA) for addr in chunk]
            calldata = _encode_try_aggregate(calls, require_success=False)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_call",
                "params": [
                    {"to": multicall_addr, "data": calldata},
                    "latest",
                ],
            }

            resp = client.post(rpc_url, json=payload)
            if resp.status_code != 200:
                continue

            raw_result = resp.json().get("result")
            if not raw_result or raw_result == "0x":
                continue

            # Multicall3 tryAggregate returns Result[](bool success, bytes returnData)
            # Manual unpacking to stay fast without full eth_abi dependency
            clean = raw_result.removeprefix("0x")
            if len(clean) < 64:
                continue

            # pointer to array
            arr_offset = int(clean[0:64], 16) * 2
            count = int(clean[arr_offset : arr_offset + 64], 16)

            for i in range(min(count, len(chunk))):
                elem_ptr = arr_offset + 64 + (i * 64)
                item_offset = arr_offset + 64 + int(clean[elem_ptr : elem_ptr + 64], 16) * 2
                success = int(clean[item_offset : item_offset + 64], 16) == 1
                if not success:
                    continue

                data_len_offset = item_offset + 128
                data_len = int(clean[data_len_offset : data_len_offset + 64], 16) * 2
                ret_data = clean[data_len_offset + 64 : data_len_offset + 64 + data_len]

                r0, r1, _ = decode_reserves_result(ret_data)
                if r0 > 0 and r1 > 0:
                    out[chunk[i].lower()] = (r0, r1)
    finally:
        if close_client:
            client.close()

    return out

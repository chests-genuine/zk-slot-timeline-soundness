# app.py
import os
import sys
import json
import time
import argparse
from typing import Dict, List, Tuple, Optional
from web3 import Web3

# Defaults (override with environment for convenience)
DEFAULT_RPC = os.environ.get("RPC_URL", "https://mainnet.infura.io/v3/YOUR_INFURA_KEY")

Slot = Tuple[str, int]  # (label, slot_index_int)


def to_checksum(addr: str) -> str:
    if not Web3.is_address(addr):
        raise ValueError(f"Invalid Ethereum address: {addr}")
    return Web3.to_checksum_address(addr)


def parse_slot_hex(raw: str) -> int:
    s = raw.strip().lower()
    if not s.startswith("0x"):
        raise ValueError(f"Slot must be 0x-prefixed hex: {raw}")
    try:
        return int(s, 16)
    except Exception:
        raise ValueError(f"Invalid slot hex: {raw}")


def parse_slots(args) -> List[Slot]:
    """
    Accepts:
      --slot label:0xSLOT   (repeatable)
      --slot 0xSLOT         (label defaults to hex)
      --manifest slots.json (list ["0x.."] or map {"label":"0x.."})
    """
    slots: List[Slot] = []

    if args.slot:
        for item in args.slot:
            if ":" in item:
                label, raw = item.split(":", 1)
            else:
                label, raw = item, item
            slots.append((label, parse_slot_hex(raw)))
        return slots

    if args.manifest:
        with open(args.manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for raw in data:
                slots.append((raw, parse_slot_hex(raw)))
        elif isinstance(data, dict):
            for label, raw in data.items():
                slots.append((label, parse_slot_hex(raw)))
        else:
            raise ValueError("Manifest must be a list of 0x-hex slots or a mapping label -> 0x-hex slot.")
        return slots

    raise ValueError("No slots provided. Use --slot (repeatable) or --manifest JSON file.")


def get_storage_at(w3: Web3, address: str, slot: int, block_id: int) -> str:
    val = w3.eth.get_storage_at(address, slot, block_identifier=block_id)
    return val.hex()


def scan_timeline(
    w3: Web3,
    address: str,
    slots: List[Slot],
    start_block: int,
    end_block: int,
    step: int,
) -> Dict[str, List[Tuple[int, str]]]:
    """
    Returns {label: [(block, value_hex), ...]} sampled over the range.
    """
    out: Dict[str, List[Tuple[int, str]]] = {lbl: [] for lbl, _ in slots}
    blocks = list(range(start_block, end_block + 1, step))
    total = len(blocks)
    for i, b in enumerate(blocks, start=1):
        pct = (i / total) * 100
         # ✅ New: Print progress with estimated time remaining
    elapsed = time.time() - start_time
    avg_time_per_block = elapsed / i if i > 0 else 0
    remaining_blocks = total - i
    eta = remaining_blocks * avg_time_per_block
    print(f"🔍 Block {b} ({i}/{total}, {pct:.1f}%) | ETA: {eta:.1f}s remaining")
        for lbl, idx in slots:
            try:
                val = get_storage_at(w3, address, idx, b)
            except Exception as e:
                val = f"ERROR:{e}"
            out[lbl].append((b, val))
    return out


def summarize_changes(series: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """
    Collapse a per-slot series to change points: [(block, value), ...]
    """
    changes: List[Tuple[int, str]] = []
    prev: Optional[str] = None
    for block, val in series:
        if val != prev:
            changes.append((block, val))
            prev = val
    return changes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="zk-slot-timeline-soundness — sample storage slots over a block range and report change points (useful for Aztec/Zama bridges, rollup state, and Web3 audits)."
    )
    p.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default: env RPC_URL)")
    p.add_argument("--address", required=True, help="Contract address to inspect")
    p.add_argument("--from-block", type=int, required=True, help="Start block (inclusive)")
    p.add_argument("--to-block", type=int, required=True, help="End block (inclusive)")
    p.add_argument("--step", type=int, default=500, help="Stride between sampled blocks (default: 500)")
    p.add_argument("--slot", action="append", help="Storage slot; repeatable. Format: 0xSLOT or label:0xSLOT")
    p.add_argument("--manifest", help="Path to JSON manifest of slots (list or map format)")
    p.add_argument("--timeout", type=int, default=30, help="RPC timeout seconds (default: 30)")
    p.add_argument("--json", action="store_true", help="Emit JSON report")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.from_block > args.to_block:
        print("❌ --from-block must be <= --to-block")
        sys.exit(1)
    if args.step <= 0:
        print("❌ --step must be positive")
        sys.exit(1)

    try:
        address = to_checksum(args.address)
        slots = parse_slots(args)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    if not args.rpc.startswith(("http://", "https://")):
        print("❌ Invalid RPC URL (must start with http/https).")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": args.timeout}))
    if not w3.is_connected():
        print("❌ RPC connection failed.")
        sys.exit(1)

    print("🔧 zk-slot-timeline-soundness")
    try:
        print(f"🧭 Chain ID: {w3.eth.chain_id}")
    except Exception:
        pass
    print(f"🔗 RPC: {args.rpc}")
    print(f"🏷️ Address: {address}")
    print(f"🧱 Range: {args.from_block} → {args.to_block} (step={args.step})")
    print(f"🗃️ Slots: {', '.join([lbl for lbl, _ in slots])}")

    t0 = time.time()
    timeline = scan_timeline(w3, address, slots, args.from_block, args.to_block, args.step)
    elapsed = round(time.time() - t0, 2)

    print("\n📜 Change Points")
    total_changes = 0
    change_report: Dict[str, List[Tuple[int, str]]] = {}
    for lbl in timeline:
        changes = summarize_changes(timeline[lbl])
        change_report[lbl] = changes
        total_changes += max(0, len(changes) - 1)  # exclude first observation
        if len(changes) == 1:
            print(f"  • {lbl}: constant value across samples (first @#{changes[0][0]})")
        else:
            print(f"  • {lbl}: {len(changes)-1} change(s)")
            for blk, val in changes:
                print(f"      - @#{blk}: {val}")

    ok = total_changes == 0
    print(f"\n{'🎯 SOUND (no changes detected)' if ok else '🚨 UNSOUND (slot value changes observed)'}")
    print(f"⏱️ Completed in {elapsed}s")

    if args.json:
        out = {
            "rpc": args.rpc,
            "address": address,
            "range": [args.from_block, args.to_block, args.step],
            "slots": [{"label": lbl, "index": hex(idx)} for lbl, idx in slots],
            "timeline": {lbl: [{"block": b, "value": v} for (b, v) in series] for lbl, series in timeline.items()},
            "change_points": {lbl: [{"block": b, "value": v} for (b, v) in change_report[lbl]] for lbl in change_report},
            "total_changes": total_changes,
            "ok": ok,
            "elapsed_seconds": elapsed,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))

    # Exit non-zero if any change detected (useful for CI)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()

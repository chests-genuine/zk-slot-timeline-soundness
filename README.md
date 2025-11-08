# zk-slot-timeline-soundness

## Overview
`zk-slot-timeline-soundness` samples **storage slots** of a contract over a block range and reports any **change points** it observes.  
This is useful for auditing critical invariants in zk ecosystems (Aztec, Zama), bridges, rollup inbox/outbox contracts, and governance vaults where slot drift can threaten **soundness**.

## Features
- Sample one or many storage slots across a block range (with a configurable stride)  
- Print per-slot **change points** (block → new value)  
- Summarize whether slots stayed **constant** or **changed**  
- JSON output for CI pipelines and monitoring dashboards  
- Deterministic, read-only checks via `eth_getStorageAt`  

## Installation
1) Python 3.9+  
2) Install dependency:
   pip install web3  
3) Optionally set a default RPC:
   export RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY

## Usage
Track a couple of slots (labelled) every 500 blocks:
   python app.py --address 0xYourContract --from-block 19000000 --to-block 20000000 --step 500 --slot owner:0x0 --slot impl:0x360894A13BA1A3210667C828492DB98DCA3E2076CC3735A920A3CA505D382BBC

Load slots from a JSON manifest (list or map):
   python app.py --address 0xYourContract --from-block 19000000 --to-block 20000000 --step 250 --manifest slots.json

Tight sampling for sensitive contracts:
   python app.py --address 0xVerifier --from-block 19999000 --to-block 20000000 --step 50

Emit machine-readable JSON:
   python app.py --address 0xYourContract --from-block 19999000 --to-block 20000000 --step 500 --json

Increase timeout for slow providers:
   python app.py --address 0xYourContract --from-block 18000000 --to-block 20000000 --step 1000 --timeout 60

## Manifest formats
List form:
[
  "0x0",
  "0x360894A13BA1A3210667C828492DB98DCA3E2076CC3735A920A3CA505D382BBC"
]

Map form:
{
  "owner": "0x0",
  "implementation": "0x360894A13BA1A3210667C828492DB98DCA3E2076CC3735A920A3CA505D382BBC"
}

## Expected Result
- The tool prints chain info, the sampled range, and progress per block.  
- For each slot, it lists **change points**; if a slot stayed constant across samples, it says so.  
- Exit code:  
  - `0` → No slot changes observed (SOUND)  
  - `2` → At least one change observed (UNSOUND)  

### Example (truncated)
🔧 zk-slot-timeline-soundness  
🧭 Chain ID: 1  
🔗 RPC: https://mainnet.infura.io/v3/…  
🏷️ Address: 0xABC…  
🧱 Range: 19000000 → 20000000 (step=500)  
🗃️ Slots: owner, implementation  
🔍 Block 19000000 (1/21, 4.8%)  
…  
📜 Change Points  
  • owner: constant value across samples (first @#19000000)  
  • implementation: 1 change(s)  
      - @#19500500: 0x0000…9f → new implementation pointer  

🚨 UNSOUND (slot value changes observed)  
⏱️ Completed in 1.21s  

## Notes
- **Why slots?** Critical invariants (e.g., proxy implementation, roots, guardians) live in deterministic storage slots; unexpected drift can break proof assumptions or enable privilege escalation.  
- **EIP-1967 proxies:** The implementation slot is commonly `0x3608…BBC`. Tracking this across time is a reliable upgrade detector.  
- **Stride trade-off:** Smaller `--step` gives higher resolution (more RPC calls); larger `--step` is faster but may miss short-lived changes between samples.  
- **Archive access:** Historical reads require archive-capable RPCs. Without archive support, old block queries may fail.  
- **JSON tips:** The report includes the full per-slot timeline and collapsed change points so you can visualize drift or alert on changes in CI.  
- **Cross-network safety:** Pair this with a cross-chain comparator to ensure an L1 ↔ L2 pair keeps the same critical state values over time.  
- **Read-only:** The tool never sends transactions; it performs safe JSON-RPC reads only.  
- **Soundness meaning here:** “SOUND” means none of the monitored slots changed within the sampled blocks; “UNSOUND” means at least one did — investigate governance events or deploy upgrades accordingly.  

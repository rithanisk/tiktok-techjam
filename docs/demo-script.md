# Three-minute demo storyboard

## 0:00–0:20 — Problem

“Shopping is not one query. It is a changing specification. Most agents append dialogue, so old preferences survive corrections and the same ten products repeat after a miss.”

## 0:20–0:45 — Architecture

Show the flow: Intent Ledger → explicit slots → posting-list intersection → safe exact-pool gate, with the progressive portfolio protecting broad-query recall. Show live-pool entropy and the flight recorder alongside it. State that the scored path is offline and uses zero model tokens.

## 0:45–1:35 — Live changing-intent session

Run:

```bash
python3 scripts/demo.py --policy adaptive
```

Show a vague request, leather/black requirements, an explicit replacement with cotton/blue, a no-brand-preference answer, and the changing route/page/latency trace.

## 1:35–2:20 — Evidence

Show committed benchmark and ablation results:

- Baseline 0.106710
- Stateful single view 0.750401
- Three-view fusion 0.765429
- Full portfolio 0.813553
- Pure facet entropy 0.862611
- Hybrid exact intersection 0.877413
- 96.5% Hit Rate@10, 2.750 MTTC, zero tokens/network

Call out all four scenarios and the public/private limitation.

## 2:20–2:45 — Robustness

Show the retrieval-timeout unit test and the flight recorder's fallback event. Mention sanitized inputs, session isolation, read-only catalog, and one-command clean setup.

## 2:45–3:00 — Close

“Intent Ledger proves that a better shopping copilot does not need a larger model. It needs state that can change, exact constraints that can narrow safely, broad retrieval that protects recall, and questions that earn their turn.”

## Recording checklist

- Keep terminal text readable at 1080p.
- Do not expose local usernames, API keys, or unrelated files.
- Use only catalog metadata and team-owned visuals.
- Upload publicly to YouTube and add the link to Devpost and `docs/project-description.md`.

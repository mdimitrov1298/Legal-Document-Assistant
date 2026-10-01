# eval-v0.1 (DRAFT)

Bulgarian evaluation package for the two tasks of the prototype: summarize with
citations and verify a claim (supported / denied / inconclusive) with verbatim
quotes. The package is a **draft**: `status` is `"draft"` and `frozen_at` is
`null` in `manifest.json`. It must be frozen (date recorded, hashes locked)
before any comparative run between models.

## Layout

```
eval-v0.1/
  manifest.json          # package metadata, passages P1 to P4, scenarios S1 to S5
  README.md
  LICENSE-NOTES.md       # provenance and reuse notes per passage
  passages/
    P1.txt               # synthetic normative-style rules (S1)
    P2.txt               # synthetic narrative of a dispute (S2)
    P4.txt               # synthetic second document on the P2 case (S4)
  claims/
    claims.jsonl         # seed claims with gold labels and evidence
  gold/
    summaries/           # reference summary pointers (empty until P3 is sourced)
```

## Passages

| ID | Status | Genre | Source | Scenarios |
|----|--------|-------|--------|-----------|
| P1 | draft | normative | synthetic | S1, S5 |
| P2 | draft | narrative | synthetic | S2, S5 |
| P3 | pending | long EU legal | EUR-Lex-Sum (bg), not sourced yet, `celex_id` null | S3, S5 |
| P4 | draft | second document, same case as P2 | synthetic | S4, S5 |

P1, P2 and P4 are **synthetic demo texts** written for this package. Every file
starts with a line saying so. People, companies, streets and the town
"Примерово" are fictional. They are not court documents and contain no
personal data.

P4 is always ingested together with its companion P2 (`companion_passages` in
the manifest), so multi-document claims can find evidence in both.

## Manifest fields

Per passage: `id`, `status`, `path`, `language`, `genre`, `source`,
`celex_id`, `license`, `split`, `retrieved_at`, `file_hash`
(`sha256:<hex>` over the raw UTF-8 bytes), `token_count_approx`
(ceil(characters / 3)), `tasks`, `scenarios`, `companion_passages`, `notes`.

## Claims

`claims/claims.jsonl` has one JSON object per line:

| Field | Meaning |
|-------|---------|
| `claim_id` | Stable key, `C01` ... |
| `passage_id` | Passage whose case the claim is checked against |
| `scenario` | S1 to S5 |
| `language` | `bg` |
| `claim_text` | The claim in Bulgarian |
| `gold_label` | `SUPPORTED`, `REFUTED` or `NEI` |
| `gold_evidence` | List of `{passage_id, char_span: [start, end], quote}`; `quote` equals `text[start:end]` of that passage; empty for NEI |
| `trap_type` | Optional: `changed_number`, `inverted_fact`, `multi_document`, `cross_document_contradiction`, `missing_fact`, `invented_date` |
| `annotator_notes` | Short rationale for the gold label |

The draft has 18 claims (6 SUPPORTED, 6 REFUTED, 6 NEI). System verdicts map
to gold labels as `supported -> SUPPORTED`, `denied -> REFUTED`,
`inconclusive -> NEI`.

## Running

From `backend/` with the venv active (see the main README for setup):

```bash
python -m app.eval.run --package ../eval/eval-v0.1 --model qwen2.5:7b \
  --num-ctx 4096 --top-k 5 --out ../eval/runs
python -m app.eval.score ../eval/runs/<run>.jsonl
```

Each passage is ingested into a temporary case in an isolated work directory
(the regular case store is not touched). The run file starts with a `run`
record (git commit, model tag, Ollama version, num_ctx, temperature, top_k,
chunk size and overlap, embedding backend and model, prompt version, package
hash, timestamp) followed by `ingest`, `summary` and `verify` records and a
`run_end` footer. Use `--repeats 3` for latency medians and `--no-stub` to
fail instead of stubbing when Ollama is down.

Runs are written to `eval/runs/` (gitignored). Runs with stubbed outputs,
failed steps or `hash_stub` embeddings are reported by the scorer as **not
valid for model comparison**. No results are committed with this draft.

## Changing the package

Any change to a passage or a gold label after freezing requires a new package
version (for example `eval-v0.2`) or an explicit changelog entry. Hashes in
the manifest are checked by the backend test suite.

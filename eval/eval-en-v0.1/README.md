# eval-en-v0.1 (DRAFT)

English evaluation package for the two tasks of the prototype: summarize with
citations and verify a claim (supported / denied / inconclusive) with verbatim
quotes. The package mirrors the structure and claim scenarios of the Bulgarian
`eval-v0.1` package but uses English passages and claims.

## Layout

```
eval-en-v0.1/
  manifest.json          # package metadata, passages P1 to P4, scenarios S1 to S5
  README.md
  LICENSE-NOTES.md       # provenance and reuse notes per passage
  passages/
    P1.txt               # English translation of eval-v0.1 P1 (normative rules, S1)
    P2.txt               # English translation of eval-v0.1 P2 (dispute narrative, S2)
    P3.txt               # EUR-Lex-Sum EN, CELEX 31998R2866 (S3)
    P4.txt               # English translation of eval-v0.1 P4 (inspection report, S4)
  claims/
    claims.jsonl         # 25 claims with gold labels and evidence
  gold/
    summaries/           # reference summaries P1.txt to P4.txt
```

## Passages

| ID | Status | Genre | Source | Scenarios |
|----|--------|-------|--------|-----------|
| P1 | draft | normative | translation of BG eval-v0.1 P1 | S1, S5 |
| P2 | draft | narrative | translation of BG eval-v0.1 P2 | S2, S5 |
| P3 | draft | long EU legal | EUR-Lex-Sum (en), CELEX 31998R2866, CC-BY-SA 4.0 | S3 |
| P4 | draft | second document, same case as P2 | translation of BG eval-v0.1 P4 | S4, S5 |

P1, P2 and P4 are **project-original English translations** of the synthetic
Bulgarian demo texts from `eval-v0.1`. The same facts and structure are
preserved so results on the two packages are directly comparable. Their
manifest entries carry `"translation_of": "eval-v0.1/P<n>"` and
`"original_language": "bg"` to make the provenance explicit. Original
English documents are tested at case level in `eval-cases-v0.1` (cases
K3 and K4).

P3 is the English version of the same EU regulation (CELEX 31998R2866) used
as P3 in the Bulgarian package, sourced from the EUR-Lex-Sum English split.

## Claims

`claims/claims.jsonl` has one JSON object per line. Same format as eval-v0.1:

| Field | Meaning |
|-------|---------|
| `claim_id` | Stable key, `C01` ... `C25` |
| `passage_id` | Passage whose case the claim is checked against |
| `scenario` | S1 to S5 |
| `language` | `en` |
| `claim_text` | The claim in English |
| `gold_label` | `SUPPORTED`, `REFUTED` or `NEI` |
| `gold_evidence` | `{passage_id, char_span, quote}`; empty for NEI |
| `trap_type` | Same types as eval-v0.1 |

25 claims, 9 SUPPORTED, 8 REFUTED, 8 NEI. Same distribution and trap types
as the Bulgarian package.

## Running

```bash
cd backend
source .venv/bin/activate
python -m app.eval.run --package ../eval/eval-en-v0.1 --model qwen2.5:7b \
  --num-ctx 4096 --top-k 5 --out ../eval/runs
python -m app.eval.score ../eval/runs/<run>.jsonl
```

# Human Faithfulness Review

## Purpose

Each review CSV contains one row per summary sentence from a run file.
A human annotator fills the empty columns to assess faithfulness.

## Columns

| Column | Pre-filled? | Description |
|--------|-------------|-------------|
| `run_file` | yes | Stem of the source run JSONL file |
| `model` | yes | Ollama model used for the run |
| `repeat` | yes | Repeat number (1, 2, 3) |
| `passage_id` | yes | Passage or case ID |
| `sentence_id` | yes | `s1`, `s2`, ... within the summary |
| `sentence` | yes | The summary sentence to evaluate |
| `cited_chunk_text` | yes | Up to 5 cited chunks (truncated) for reference |
| `faithful` | **no** | 1–5 Likert scale (1 = hallucinated, 5 = fully faithful) |
| `error_type` | **no** | `name`, `date`, `number`, `qualification`, `unsupported`, or `none` |
| `comment` | **no** | Free-text note from the annotator |

## Annotation guidelines (Deroy et al. 2023 style)

1. Read the summary sentence.
2. Check whether every fact in the sentence is supported by the cited chunks
   and/or the full source passage.
3. Rate faithfulness on a 1–5 Likert scale:
   - **5** — fully supported by evidence, no factual error.
   - **4** — mostly supported, minor imprecision (e.g. rounding).
   - **3** — partially supported; some facts present, others added or vague.
   - **2** — significant unsupported claim or factual error.
   - **1** — hallucinated or contradicts the source.
4. If faithfulness < 5, choose the most specific `error_type`.
5. Add a brief `comment` explaining any error.

## Generating sheets

```bash
cd backend
python -m app.eval.review_sheet ../eval/runs/<run>.jsonl --out ../eval/reviews/<run>.csv
```

## Scoring

```bash
cd backend
python -m app.eval.review_score ../eval/reviews/<name>.csv [--json]
```

Reports mean Likert, error share and error count per model.

## Template

See `TEMPLATE.csv` for the column layout.

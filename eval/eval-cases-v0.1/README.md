# eval-cases-v0.1 (DRAFT)

Case-level evaluation package for Задача 4 ("Провеждане на тестове с примерни казуси").
Each case contains multiple documents uploaded together and is tested end to end:
create case → upload documents → ingest → summarize → verify → ask → search.

## Cases

| Case | Language | Documents | Claims | Questions | Source |
|------|----------|-----------|--------|-----------|--------|
| K1-bg-uslugi | BG | 3 TXT (contract, acceptance protocol, witness statement) | 12 | 6 | Project-original synthetic |
| K2-bg-pokriv | BG | 2 TXT + 1 PDF (roof repair dispute: statement of facts, inspection report) | 10 | 5 | Project-original synthetic |
| K3-en-service | EN | 2 TXT + 1 PDF (IT service agreement + breach letter) | 12 | 7 | Project-original synthetic |
| K4-en-eurlex | EN | 2 TXT + 1 PDF (Paris Agreement decision + Forced Labour Protocol decision) | 10 | 5 | EUR-Lex-Sum (CC-BY-SA 4.0) |

**Total:** 44 claims, 23 questions, 12 documents across 4 cases in 2 languages.
At least one PDF per language (condition 1). All documents are public or project-original
synthetic (condition 4). No personal data.

## Layout

```
eval-cases-v0.1/
  manifest.json
  README.md
  LICENSE-NOTES.md
  cases/
    K1-bg-uslugi/
      documents/          # 3 BG demo files
      gold_summary.txt
      claims.jsonl        # 12 claims
      questions.jsonl     # 6 questions
    K2-bg-pokriv/
      documents/          # 2 TXT + 1 PDF
      gold_summary.txt
      claims.jsonl        # 10 claims
      questions.jsonl     # 5 questions
    K3-en-service/
      documents/          # 2 TXT + 1 PDF
      gold_summary.txt
      claims.jsonl        # 12 claims
      questions.jsonl     # 7 questions
    K4-en-eurlex/
      documents/          # 2 TXT + 1 PDF
      gold_summary.txt
      claims.jsonl        # 10 claims
      questions.jsonl     # 5 questions
```

## Claims format

Each line in `claims.jsonl`:
```json
{"claim_id": "C01", "claim_text": "...", "gold_label": "SUPPORTED|REFUTED|NEI",
 "gold_evidence": [{"document": "filename.txt", "char_span": [start, end], "quote": "..."}],
 "scenario": "K1", "trap_type": null|"changed_number"|"changed_date"|...}
```

## Questions format

Each line in `questions.jsonl`:
```json
{"q_id": "Q01", "question": "...", "gold_answer": "...|not_found",
 "answer_type": "number|date|name|text|not_found",
 "gold_evidence": [{"document": "filename.txt", "char_span": [start, end], "quote": "..."}]}
```

## Running

```bash
cd backend
source .venv/bin/activate
python -m app.eval.run_cases --package ../eval/eval-cases-v0.1 --out ../eval/runs \
  --model qwen2.5:7b --repeats 3 --no-stub
python -m app.eval.score_cases ../eval/runs/<run>.jsonl
```

## PDFs

PDFs are generated from TXT sources using `scripts/make_pdf.py` (reportlab).
SHA-256 hashes are recorded in `manifest.json`.

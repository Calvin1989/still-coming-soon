# Still Coming Soon

Papers say “code will be released.” This project checks whether it was.

It finds accepted conference papers on arXiv, works out which GitHub repository each paper calls its own, and checks every day whether that repository actually contains code.

**First results.** Among accepted 2025 papers that link their own GitHub repository, the share whose repository still has no code:

| Conference | Papers with their own repository | Not delivered |
|---|---|---|
| ICML 2025 | 784 | 28 (3.6%) |
| ICLR 2025 | 1,022 | 39 (3.8%) |
| NeurIPS 2025 | 1,410 | 57 (4.0%) |
| CVPR 2025 | 655 | 49 (7.5%) |
| ACL 2025 | 613 | 48 (7.8%) |
| ICCV 2025 | 597 | 49 (8.2%) |
| ACM MM 2025 | 153 | 16 (10.5%) |
| EMNLP 2025 | 610 | 64 (10.5%) |
| AAAI 2025 | 481 | 51 (10.6%) |
| IJCAI 2025 | 143 | 17 (11.9%) |

Machine learning conferences (ICML, ICLR, NeurIPS) are around 4%. Vision and ACL are around 8%. EMNLP, ACM MM, AAAI and IJCAI are above 10%. Checked on 2026-11-08; more in [Results](#results). The 2026 conferences are being added as they pass 90 days.

## How it works

```
arXiv API ──► papers ──► full text (arXiv HTML) ──► the paper's own repo ──► git shallow clone ──► status
```

1. **Papers.** Search arXiv for papers whose comment says they were accepted at the venue (e.g. `Accepted at ICLR 2025`). Workshop papers and papers “under review” are excluded, sentence by sentence.
2. **Full text.** Read the arXiv HTML version of each paper. It keeps the structure, so the abstract, footnotes and references can be told apart.
3. **The paper's own repository.** Links in the abstract or the title block count. A link in the body only counts when its sentence talks about the authors' own work (“Our code is available at …”, “Code: …”), and not when it says the code builds on someone else's. Links in the references never count.
4. **Status.** Shallow-clone the default branch (no GitHub API quota needed) and look at the files in the latest commit:

| Status | Rule |
|---|---|
| Code released | Source files add up to ≥ 5 KB |
| A few lines of code | Some source files, < 5 KB |
| Data only | No source files, ≥ 100 KB of data or model files |
| Empty repository | Only a README, a license or images |
| Repository gone | Repository does not exist or is private |
| Anonymous link only | Final version still links only to anonymous.4open.science |
| No repository link | Paper says code will be released, but we found no repository link in it |

All thresholds live in [`pipeline/config.toml`](pipeline/config.toml).

## What this project does not do

- It does not show author names and does not judge anyone. A repository can be empty for good reasons.
- It only checks the default branch. If the code is elsewhere, please [open an issue](../../issues) and we will fix the entry.

## Run it yourself

Python 3.11+, standard library only, plus `git`.

```bash
cd pipeline
python -m scs papers   --venue iclr2025   # arXiv API → data/papers/
python -m scs fulltext --venue iclr2025   # arXiv HTML → data/fulltext/ (3 s per paper)
python -m scs links    --venue iclr2025   # → data/links/
python -m scs probe    --venue iclr2025   # git clone → data/snapshots/
python -m scs build    --venue iclr2025   # → data/site/
python -m scs render                      # all venues → public/
```

Each step reads the previous step's files and can be re-run on its own. Data files are JSON Lines and are committed, so the git history is the daily record.

Tests: `pip install pytest ruff && ruff check . && pytest` (no network needed).

## Adding a venue

Add a `[venues.<key>]` section to `pipeline/config.toml` with the arXiv query and the conference date. Nothing else needs changing: the workflows ask `python -m scs venues` which venues to handle.

- Once the conference has opened, the monthly job starts collecting its papers.
- `[schedule] wait_days` (90) days after it opened, it appears on the site and is checked daily. Until then the front page lists it with the date it will appear.

Venues for 2026 are already configured (AAAI, ICLR, CVPR, ICML, ACL, IJCAI, ECCV, EMNLP, ACM MM, NeurIPS) and come online on their own.

## Results

Measured on 2026-11-08, from the full text of every paper (arXiv HTML version).

| Conference | Accepted papers found on arXiv | With their own repository | Empty | A few lines | Gone | Not delivered |
|---|---|---|---|---|---|---|
| ICML 2025 | 1,319 | 784 | 20 | 1 | 7 | 3.6% |
| ICLR 2025 | 1,626 | 1,022 | 23 | 5 | 11 | 3.8% |
| NeurIPS 2025 | 2,345 | 1,410 | 39 | 1 | 17 | 4.0% |
| CVPR 2025 | 1,393 | 655 | 37 | 6 | 6 | 7.5% |
| ACL 2025 | 946 | 613 | 38 | 3 | 7 | 7.8% |
| ICCV 2025 | 1,198 | 597 | 39 | 1 | 9 | 8.2% |
| ACM MM 2025 | 292 | 153 | 13 | 0 | 3 | 10.5% |
| EMNLP 2025 | 926 | 610 | 50 | 4 | 10 | 10.5% |
| AAAI 2025 | 1,205 | 481 | 36 | 6 | 9 | 10.6% |
| IJCAI 2025 | 297 | 143 | 12 | 1 | 4 | 11.9% |

- Not counted as not delivered: repositories with data only, links described only as a project page, and papers whose arXiv version gives no repository or only an anonymous review link (it may still be the double-blind review version).
- Every “repository gone” entry was checked by hand after the first full run of each conference. Extraction errors found this way (URLs written together, LaTeX leftovers in names, placeholder `github.com/anonymous/…` links) were fixed and are covered by tests.

## License

Code: MIT. Data comes from arXiv and public GitHub repositories.

# Still Coming Soon

Papers say “code will be released.” This project checks whether it was.

It finds accepted conference papers on arXiv, works out which GitHub repository each paper calls its own, and checks every day whether that repository actually contains code.

**First results.** Among accepted 2025 papers that link their own GitHub repository, the share whose repository still has no code:

| Conference | Papers with their own repository | Not delivered |
|---|---|---|
| ICLR 2025 | 613 | 20 (3.3%) |
| CVPR 2025 | 472 | 37 (7.8%) |
| AAAI 2025 | 303 | 29 (9.6%) |

Checked on 2026-11-08. More in [Results](#results).

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

Add a `[venues.<key>]` section to `pipeline/config.toml` with the arXiv query and the conference date, then add the key to `VENUES` in `.github/workflows/*.yml`.

## Results

Measured on 2026-11-08.

| Conference | Accepted papers found on arXiv | With their own repository | Empty | A few lines | Gone | Not delivered |
|---|---|---|---|---|---|---|
| ICLR 2025 | 1,626 | 613 | 15 | 3 | 2 | 3.3% |
| CVPR 2025 | 1,393 | 472 | 28 | 4 | 5 | 7.8% |
| AAAI 2025 | 1,205 | 303 | 22 | 3 | 4 | 9.6% |

- Repository links come from the full text for a random sample (300 ICLR papers, 150 CVPR, 150 AAAI) and from the arXiv abstract for the rest. On the samples, the full-text rates agree with the table (4.8%, 8.2%, 7.2%). The full run happens in `monthly.yml`.
- The difference between ICLR and the other two is statistically significant (two-proportion z ≈ 3.3 and 4.0).
- Not counted as not delivered: repositories with data only, links described only as a project page, and papers whose arXiv version gives no repository (it may still be the double-blind review version).

## License

Code: MIT. Data comes from arXiv and public GitHub repositories.

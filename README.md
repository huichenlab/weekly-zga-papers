# Weekly ZGA/MZT Papers

This private GitHub Actions project searches each week for research and review papers related to zygotic genome activation (ZGA), embryonic genome activation, and the maternal-to-zygotic transition (MZT). It creates a cited landscape infographic PDF, develops testable early-*Xenopus* grant ideas, archives the PDF and structured evidence in GitHub, and optionally emails the PDF to `huic@sc.edu`.

## Schedule

The workflow runs every Friday at 12:00 PM America/New_York. Because GitHub cron uses UTC, it starts at both possible UTC equivalents and proceeds only when the runner confirms that local Eastern time is Friday noon. It can also be launched manually from **Actions > Weekly ZGA and MZT papers > Run workflow**.

## No ChatGPT/OpenAI credits

This project does not call ChatGPT or the OpenAI API and does not need an OpenAI key. Literature discovery uses public Europe PMC and Crossref APIs. Scientific synthesis runs locally inside the GitHub Actions runner with Ollama and `qwen3:4b`.

GitHub Actions minutes and storage are governed by the repository owner's GitHub plan. The first run downloads an approximately 2.5 GB local model and is expected to take longer than later runs.

## Included literature

- peer-reviewed primary research;
- methods/resource papers with original results;
- peer-reviewed narrative and systematic reviews;
- scholarly review/perspective hybrids;
- relevant preprints, labeled as not peer reviewed.

The report separates research, reviews, and preprints. Review syntheses are not presented as new experimental discoveries. Search concepts include ZGA/EGA, MZT, maternal RNA clearance, minor/major ZGA, early embryonic transcription, and closely related mechanisms.

## Outputs saved in GitHub

- `pdf/<year>/zga_mzt_weekly_<date>.pdf` - final infographic;
- `reports/<year>/zga_mzt_weekly_<date>.json` - structured source evidence and analysis;
- `state/weekly_state.json` - deduplication, report, QA, and email state.

Every PDF is rendered to PNG internally with Poppler and checked for page count, landscape layout, extractable text, blank pages, and content touching page edges before it is committed.

## Email setup

In **Settings > Secrets and variables > Actions**, add:

- `SMTP_USERNAME` - the Gmail sender address, such as `huichenlab@gmail.com`;
- `SMTP_PASSWORD` - a Gmail app password, not the regular Gmail password.

If these secrets are absent, PDF generation and GitHub archival still run. Email remains marked `pending`. SMTP `verified` means Gmail accepted the message; it does not guarantee inbox placement.

## Scientific limits

The automated pipeline uses publicly available metadata and abstracts and does not claim full-text review unless a future source integration explicitly provides authorized full text. Its grant ideas are hypotheses, not preliminary data. Expert review is required before using the output in a proposal.

## Local validation

```bash
python -m pip install -r requirements.txt
pytest -q
```

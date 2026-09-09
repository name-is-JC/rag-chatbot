# Decision Log

Running record of decisions, trade-offs, compromises, and discoveries made throughout this project. Maintained phase-by-phase, starting 2026-09-09. Source material for the Phase 6 case study and project reference doc — not the final polished documents themselves.

---

## Product & Scope

- **Product context:** Groww, chosen by the user from a shortlist (INDMoney, Groww, PowerUp Money, Wealth Monitor, Kuvera).
- **AMC:** Bajaj Finserv Mutual Fund.
- **Schemes:** 7 — Small Cap, Flexi Cap, Healthcare (sectoral), Multi Cap, Large & Mid Cap, Balanced Advantage (hybrid), ELSS Tax Saver.
  - **Compromise:** problem statement called for 3–5 schemes; user explicitly accepted expanding to 7 to ensure ELSS lock-in coverage (an ELSS scheme was missing from the initial 6-scheme list and was added deliberately).
- **Source authority compromise:** all 7 confirmed source URLs are `groww.in` pages (a retail platform), not the AMC's own site, AMFI, or SEBI — which the problem statement's "official sources only" constraint technically excludes. User explicitly accepted this as a deviation rather than switching to official AMC/AMFI/SEBI pages. Documented in [RAG-Architecture.md §2.3](./RAG-Architecture.md#23-accepted-deviations-from-the-problem-statement-explicitly-confirmed-by-user-not-assumed).

## Technology Stack (confirmed via explicit options, not assumed)

- **Language:** Python — chosen to keep Streamlit + Chroma + local embeddings in one ecosystem.
- **LLM (generation):** Grok (xAI API) — OpenAI-compatible REST API.
- **Embeddings:** local `sentence-transformers` (`all-MiniLM-L6-v2`) — free, offline, no API key; this is Chroma's default embedding function.
- **Vector store:** Chroma (local, persistent) — appropriate for a small (~15-25 doc) corpus; cosine similarity space set explicitly (Chroma defaults to L2, which is a worse fit for these embeddings).
- **UI:** Streamlit, with multi-thread/session chat support required.
- **Scheduler:** GitHub Actions — chosen over `APScheduler`/Windows Task Scheduler once we needed a mechanism that fires reliably without a continuously-running local process.
  - **Compromise:** this is a deliberate, narrow exception to the project's "everything inside the project folder, no other storage/location" rule, since Actions runs on GitHub's cloud — scoped to compute only, since the resulting data is committed back into the same repo.

## Phase 1 — Scheduler

- Schedule confirmed: Mon–Fri, 9:15 AM IST (`cron: "45 3 * * 1-5"` UTC) — timed to NSE/BSE market open.
- **Persistence strategy decision:** commit ingested data back to the git repo, rather than GitHub Actions cache/artifacts — cache/artifacts are built for CI speedups and expire; committing keeps the repo as the single source of truth and gives a free audit trail via `git log`, appropriate at this corpus size (no Git LFS needed).
- **Folder structure correction:** initially organized code by function only (`.github/workflows/`, `src/ingestion/`, etc.) without a phase-labeled folder. User corrected this — wanted explicit `phase-N-name/` folders holding each phase's actual code. Reconciled with GitHub's hard requirement that workflow trigger files must live at `.github/workflows/` at the repo root: that file stays thin and calls into `phase-1-scheduler/`.
- **Verification approach:** rather than just writing the workflow and asserting it works, manually triggered it and watched it reach `success`, then separately observed the *real* cron trigger fire unattended on schedule (2026-09-08, 2026-09-09) — both are visible in the repo's Actions tab as durable proof, not just a claim.

## Phase 2 — Ingestion

- **Chunking strategy — explicit choice with a stated trade-off:** generic fixed-size chunking (200 tokens/40 overlap), applied uniformly to all source types, chosen over field-level extraction or a hybrid approach. Known trade-off accepted: a fixed-size window can occasionally split a label from its value.
- **Major discovery mid-implementation:** the first working version of the HTML parser was actually scraping Groww's site navigation menu, not the real fund data — the actual facts are rendered client-side from an embedded `__NEXT_DATA__` JSON blob (a Next.js SSR payload), not from readily-scrapeable visible text.
  - **Resolution:** rather than trying to patch HTML-text scraping (fragile, would keep missing data), pivoted the parser to extract structured fields directly from that JSON, then render them as plain text and feed that into the *same* generic chunker already decided on. Framed and confirmed with the user as a parsing correctness fix, not a reopening of the chunking-strategy decision.
- **Second discovery:** change-detection based on hashing raw HTML never worked, because Cloudflare's email-obfuscation script re-randomizes an XOR key on every single request (for an unrelated footer contact email) — making the raw HTML hash "change" on every fetch regardless of whether the actual fund data changed.
  - **Resolution:** hash the *parsed* content instead of the raw HTML. Verified with a two-run test (full refresh, then a second run correctly reporting all sources "unchanged").
- **Data completeness gap found after initial "complete" pass:** user asked for NAV, Minimum SIP, Fund size, Expense Ratio, Rating as the important fields. NAV/SIP/Fund size/Expense Ratio were already captured; Rating (`groww_rating`) was missing entirely and was added afterward.
- **Resilience verified, not assumed:** deliberately tested a broken/nonexistent URL and confirmed it fails that one source cleanly without crashing the batch — matching the "keep last good cache" principle from the architecture doc. This was also observed for real during testing when a transient local DNS failure took down 4 of 7 sources on one run; the other 3 succeeded and the failed 4 recovered cleanly on retry.
- **Delete-and-reinsert per source** (not per-chunk upsert) on any content change — chosen because chunk boundaries can shift entirely when a page's content changes, making per-chunk upserts fragile.

## Documentation & Process Decisions

- User set a hard collaboration rule early on: no unilateral decisions — every non-trivial choice must be presented as options or explicitly confirmed. This shaped the entire project's working style (frequent confirmation checkpoints, defaults always flagged as "proposed" rather than assumed).
- Phase gating: each phase must be explicitly confirmed by the user before the next begins.
- Added Phase 6 deliverables (2026-09-09): a detailed case-study document (this log feeds into it) and a project reference/study-guide document (tools, APIs, functions, models — why/where used, plus a full step-by-step walkthrough of how the chatbot works), both to be delivered as PDFs in `Docs/`, intended for the user's PM portfolio and interview preparation respectively.

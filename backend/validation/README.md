# Validation recorded on 2026-09-24

- Backend: **14 tests passed** (`python -m pytest backend/tests -q`).
- Frontend: typecheck, ESLint and production build passed.
- Chromium: **3 browser tests passed** (`npm run test:e2e`), using a mocked API.
- Live integration smoke: Vite + Uvicorn + the real MiniLM/FAISS artifact returned
  HTTP 200, 50 hits with ranks 1–50, and no browser JavaScript errors after uploading
  the bundled frontend demo tickets. The evidence panel was visually inspected.
- Training downloader: pinned snapshot SHA-256 verified successfully.
- Real build: 20,000 historical rows → 173 document groups → 178 chunk vectors.

`baseline-parity.json` compares the public retriever against the previous NumPy
MiniLM SDC→SDC experiment on the 20 challenge queries. All 20 Top-50 candidate sets
match; 19 full rankings match exactly. Query 20 swaps ranks 15/16, whose reference
scores were exactly tied; maximum per-document error is below 1e-6. All Top-10
rankings match. The script allows near-tie rank differences only within 1e-6 and
requires per-document score error below 1e-5.

This measures migration parity, not ground-truth accuracy or downstream routing
quality. The previous experiment files are external research artifacts, not required
for routine unit tests or running the application. Build/model/data versions and
checksums are saved in the generated manifest; large artifacts are not committed.

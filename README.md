# WePlay UID Lookup API — Vercel root-file layout

This package is designed for the exact root-level GitHub layout shown in
your screenshot:

- `README.md`
- `index.py`
- `requirements.txt`
- `vercel.json`

It uses Playwright with Chromium downloaded during the Vercel install step.
No external browser service or browser token is required.

## Deploy
1. Put these four files directly in the GitHub repository root (not inside
   an `api/` folder).
2. Import the repository into Vercel.
3. Deploy using the included `vercel.json`.
4. Test `/health`, then `/lookup?uid=92661060`.

## Endpoints
- `GET /health`
- `GET /lookup?uid=92661060`
- `POST /lookup` with JSON body `{"uid":"92661060"}`

## Important
The browser is downloaded during the build, not embedded in this ZIP.
Vercel may reject or fail to run the browser if function bundle-size,
runtime-library, or execution-time limits are exceeded. Check deployment
build/runtime logs if it fails. WePlay may also change its page selectors.
Add authentication and rate limiting before exposing the endpoint publicly.

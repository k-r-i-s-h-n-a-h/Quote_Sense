This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy on Vercel (QA / test)

Workflow: `.github/workflows/deploy_test.yml` (branch `test`).

**Vercel project (`tatvaops-quotesense-qa`) must match CI:**

| Setting | Required value |
|--------|----------------|
| Root Directory | **empty** (`./`) — same as Dev |
| CI working directory | `frontend/` |
| Deploy style | `vercel pull` → `vercel build --prod` → `vercel deploy --prebuilt --prod` |

Do **not** set Root Directory to `frontend` with this workflow (that becomes `frontend/frontend` or “No Next.js version detected”).

```bash
git fetch origin
git checkout test
git reset --hard origin/dev   # optional: make test identical to dev
# apply workflow/docs commits if needed
git push --force-with-lease origin test
```

Secrets: `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_TEST`, `VERCEL_TOKEN`.

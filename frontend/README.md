This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.



If you **cleared** Root Directory to `./` (like Dev), then this README + current `deploy_test.yml` are wrong—you’d need the Dev-style “deploy from `frontend/`” flow instead. Confirm which setting you saved in the dashboard.

---

### Finalized quotes: can we identify them?

**Yes.** Same path as Dev:

- Flag: `isFinalizeQuote` (and aliases) on the Tatva quote payload  
- UI: separate FINALIZED badge  
- MA write: only via `POST /api/market-rate/apply-finalized` → `apply_finalized_quotes_to_market_rates()`  
- Compare sessions **do not** write MA  

On project load, `/api/projects/[projectId]/quotes` calls apply and exposes `X-Market-Rate-Apply` (e.g. `quotes_applied=1`).

---

### How many finalized quotes are waiting to update MA?

I **cannot** give a live count from here (no access to Tatva/Supabase staging). Check in order:

1. **Already applied?** In Supabase SQL:
```sql
SELECT session_id, COUNT(*) 
FROM market_moving_avg_sessions
WHERE session_id LIKE 'finalize:%'
GROUP BY 1
ORDER BY 1;

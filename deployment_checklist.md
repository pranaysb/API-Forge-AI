# Deployment Checklist

## Supabase (Database)
- [ ] Create a new Supabase project.
- [ ] In Database Settings, locate your Connection String.
- [ ] Enable the IPv4 connection pooler (port 6543) so LangGraph doesn't exhaust the connection limit.
- [ ] Copy the connection string to use as your `DATABASE_URL`.

## Render (Backend)
- [ ] Connect your GitHub repository to Render.
- [ ] Select the `render.yaml` configuration (Blueprint) or manually create a Web Service.
- [ ] Set Build Command: `cd backend && pip install poetry && poetry install --no-dev`
- [ ] Set Start Command: `cd backend && poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Configure Environment Variables:
  - `DATABASE_URL` = your Supabase connection string
  - `FRONTEND_URL` = the URL where your frontend will be deployed
  - `GROQ_API_KEY` = your Groq API key
  - `E2B_API_KEY` = your E2B API key (optional)
  - `PYTHON_VERSION` = `3.11.0`
- [ ] Deploy and copy the Render URL.

## Vercel (Frontend)
- [ ] Connect your GitHub repository to Vercel.
- [ ] Set the Framework Preset to Next.js.
- [ ] Set the Root Directory to `frontend`.
- [ ] Configure Environment Variables:
  - `NEXT_PUBLIC_API_URL` = your Render backend URL (e.g., `https://apiforge-backend.onrender.com`)
- [ ] Deploy and copy the Vercel URL.

## Post-Deployment
- [ ] Update Render's `FRONTEND_URL` env variable with your final Vercel URL if you didn't have it beforehand.
- [ ] Test uploading an OpenAPI spec via the deployed frontend!

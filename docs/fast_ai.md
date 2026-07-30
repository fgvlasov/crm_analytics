# Fast AI (Phase 3)

Enable with `FEATURE_FAST_AI=true`.

## Flow

1. Configure an AI provider (mock or OpenAI-compatible) via Dashboard → AI Providers or `POST /api/v1/providers`.
2. Queue Fast Assessment: `POST /api/v1/leads/{id}/assessments/queue`.
3. Worker (`app.scripts.worker_loop`) claims queued jobs and persists validated results.
4. If `FEATURE_ODOO_CONNECTOR=true` and the lead is linked to Odoo, SaaS pushes a webhook callback.

Odoo lead upsert also enqueues a fast job automatically when Fast AI is enabled.

## Safety

- Strict JSON schema validation
- Server-side score clamp and temperature
- Fingerprints skip unchanged inputs unless `force=true`
- API keys encrypted; never returned after save
- Prompt treats lead text as data, not instructions

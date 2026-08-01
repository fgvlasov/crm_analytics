# Fast AI (Phase 3)

Enable with `FEATURE_FAST_AI=true`.

## Flow

1. Configure an AI provider (mock or OpenAI-compatible) via Dashboard → AI Providers or `POST /api/v1/providers`.
2. Queue Fast Assessment: `POST /api/v1/leads/{id}/assessments/queue`.
3. Worker (`app.scripts.worker_loop`) claims queued jobs and persists validated results.
4. If `FEATURE_ODOO_CONNECTOR=true` and the lead is linked to Odoo, SaaS pushes a webhook callback.

Odoo lead upsert also enqueues a fast job automatically when Fast AI is enabled.

## OpenAI integration notes

Fast Assessment uses the **Chat Completions** API (`POST /v1/chat/completions`) with
strict Structured Outputs (`response_format: json_schema`). The complete assessment
schema is sent to the provider, and one repair attempt is made if a compatible provider
still returns an invalid object.

It does **not** use the [Agents SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart) — that product is for multi-agent tool workflows, not our structured scoring path.

**Provider Test** calls `GET /v1/models` to verify the API key without spending completion tokens.

If you see **HTTP 429 Too Many Requests** during scoring:

1. Open [OpenAI usage / billing](https://platform.openai.com/usage)
2. Confirm the project has quota/credits and is not hard-limited
3. Wait for rate-limit windows to reset, or use a different key/project
4. You can keep using the **mock** provider for end-to-end sync tests without OpenAI

## Safety

- Strict JSON schema validation
- Server-side score clamp and temperature
- Fingerprints skip unchanged inputs unless `force=true`
- Failed or cancelled jobs can be queued again after transient provider errors
- API keys encrypted; never returned after save
- Prompt treats lead text as data, not instructions

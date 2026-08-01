# Deep Research (Phase 4)

Enable both dependent features:

```env
FEATURE_FAST_AI=true
FEATURE_DEEP_RESEARCH=true
```

The API refuses to start when Deep Research is enabled without Fast AI.

## Flow

1. Complete a successful Fast Assessment for the lead.
2. When Fast Assessment recommends deeper research, the service queues it automatically.
   It can also be queued explicitly with `POST /api/v1/leads/{lead_id}/assessments/queue`
   and `{"assessment_mode":"deep"}`.
3. The worker combines the Fast Assessment, normalized lead data, up to 20 internal
   history items, up to 20 tenant-scoped similar-deal candidates, tenant profile data,
   and optional public-web research.
4. Strict schema validation rejects unknown similar-deal IDs and invalid evidence.
5. The result and private evidence metadata are persisted. Evidence objects use
   tenant-scoped S3 keys and are available only through short-lived signed URLs.
6. When the Odoo connector is enabled, the result is sent through the existing signed
   callback.

## Stale inputs

The queue fingerprint covers every Deep Research input. An unchanged non-forced request
reuses the succeeded result. If lead or Fast Assessment data changes after queueing, the
old job is marked stale/cancelled and a fresh job is queued automatically. A new
successful Fast Assessment also queues a new Deep Research job when the changed lead
still meets the recommendation threshold.

## Web research

The default web research provider is disabled and performs no network calls. The
provider protocol in `app/integrations/web_research.py` is the extension point for a
tenant-approved search service. External content is always treated as untrusted data.

## API

- `GET /api/v1/leads/{lead_id}/assessments/deep/latest`
- `GET /api/v1/assessments/{assessment_id}/evidence`
- `POST /api/v1/evidence/{evidence_id}/signed-url`

All routes return `403 feature_disabled` when Deep Research is off. Worker polling skips
Deep Research jobs when the feature is disabled.

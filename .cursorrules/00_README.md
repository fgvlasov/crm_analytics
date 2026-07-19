# AI Lead Intelligence SaaS — Cursor Requirements Pack

Этот пакет файлов предназначен для разработки в Cursor. Положи всю папку `.cursorrules/` в корень нового репозитория или скопируй файлы в существующий monorepo.

## Цель продукта

Создать независимый SaaS-сервис для B2B lead intelligence и lead scoring, который подключается к Odoo 19 клиентов через отдельный интеграционный модуль, собирает лиды из Odoo, тендерных порталов, новостей, каталогов и тематических сайтов, обогащает их AI-аналитикой и возвращает результаты в Odoo и веб-дашборд клиента.

## Главные системы

1. **Odoo Integration Module**  
   Устанавливается в Odoo 19 клиента. Отвечает за безопасную связь Odoo ↔ SaaS, синхронизацию CRM Leads/Opportunities, отображение AI-оценок и webhooks.

2. **Analytics Backend SaaS**  
   Центральный backend: tenants, users, subscriptions, Odoo instances, AI providers, scoring jobs, lead enrichment, source collectors, audit logs.

3. **Client Dashboard**  
   Отдельный web portal на домене сервиса. Клиенты входят в личный кабинет, подключают Odoo, настраивают AI keys, источники лидов, тендерные порталы, аналитику сайтов и смотрят результаты.

4. **Tender Collectors**  
   Первый поток поиска лидов. Для тестов — Smart RPT: `https://smart.rpt.fi/login`. Нужно поддержать login-based scraping/RPA, scheduled collection, deduplication, evidence storage.

5. **Web / News / Directory Collectors**  
   Второй поток поиска лидов. Аналитика новостных сайтов, каталогов, тематических площадок, отраслевых публикаций, строительных проектов, инвестиционных новостей.

6. **AI Provider Layer**  
   Каждый клиент может подключить свои ключи к OpenAI, Azure OpenAI, OpenAI-compatible gateway, Gemini, Anthropic или корпоративному AI provider. Coldex использует OpenAI для аналитики.

## Как использовать с Cursor

Начинай с файлов в таком порядке:

1. `01_PRODUCT_REQUIREMENTS.md`
2. `02_SYSTEM_ARCHITECTURE.md`
3. `03_MONOREPO_STRUCTURE.md`
4. `04_DATA_MODEL.md`
5. `05_API_CONTRACTS.md`
6. `06_ODOO_MODULE_REQUIREMENTS.md`
7. `07_BACKEND_REQUIREMENTS.md`
8. `08_DASHBOARD_REQUIREMENTS.md`
9. `09_TENDER_COLLECTORS.md`
10. `10_WEB_NEWS_COLLECTORS.md`
11. `11_AI_ANALYTICS_REQUIREMENTS.md`
12. `12_SECURITY_COMPLIANCE.md`
13. `13_SUBSCRIPTION_BILLING.md`
14. `14_DEVOPS_DEPLOYMENT.md`
15. `15_TESTING_ACCEPTANCE.md`
16. `16_ROADMAP_TASKS_FOR_CURSOR.md` — детальный backlog (legacy numbering)
17. `17_CURSOR_BOOTSTRAP_PROMPTS.md` — готовые промпты по фазам
18. `18_PHASED_DEVELOPMENT_PLAN.md` — **главный порядок разработки** и feature flags

Перед началом реализации прочитай `18_PHASED_DEVELOPMENT_PLAN.md`: там шесть фаз (каждая должна работать end-to-end) и env-флаги для включения/выключения фаз 2–6. Фаза 1 (monorepo / backend / tenants / auth) всегда включена.

```env
FEATURE_ODOO_CONNECTOR=false
FEATURE_FAST_AI=false
FEATURE_DEEP_RESEARCH=false
FEATURE_SMART_RPT=false
FEATURE_WEB_NEWS_COLLECTORS=false
```

## Development principle

Всегда строить production-grade multi-tenant SaaS, а не single-company скрипт для Coldex.

Coldex должен быть первым tenant/demo customer, но в коде не должно быть hard-code под Coldex, кроме seed/demo-конфигурации.

## Preferred stack

Если пользователь не задаст другое, использовать:

- Backend API: Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- DB: PostgreSQL 16+
- Queue: Redis + Celery или Dramatiq
- Browser automation: Playwright workers
- Object storage: S3-compatible storage, MinIO for local dev
- Dashboard: Next.js + TypeScript + Tailwind + shadcn/ui
- Odoo module: Odoo 19 Python addon
- Auth: first-party email/password + optional Google/Microsoft SSO later
- Secrets: encrypted at rest with tenant-scoped key wrapping
- Deployment: Docker Compose first, Kubernetes later

## Non-negotiable rules

- No tenant data leakage.
- No plaintext AI keys, Odoo passwords, portal credentials or session cookies.
- No scraping credentials in logs.
- All AI outputs must be validated against strict schemas before saving.
- All crawler/scraper actions must preserve source evidence.
- Every scoring result must explain why the score was assigned.
- Odoo module must remain usable if SaaS is temporarily unavailable.
- Long-running operations must run via queue, not inside HTTP request lifecycle.

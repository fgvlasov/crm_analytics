# Tenant isolation

Every tenant-scoped query must filter by `tenant_id`. Cross-tenant access returns 404.

Phase 1 tests cover:

- login scoped to tenant slug
- secrets listed only for current tenant
- fetching another tenant by id is denied

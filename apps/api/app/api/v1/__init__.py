from fastapi import APIRouter

from app.api.v1 import auth, features, jobs, leads, odoo, providers, tenants

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(features.router)
api_router.include_router(odoo.router)
api_router.include_router(leads.router)
api_router.include_router(providers.router)
api_router.include_router(jobs.router)

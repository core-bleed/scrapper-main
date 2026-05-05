from fastapi import APIRouter

from app.api.v1 import (
    bulk,
    capture,
    companies,
    contacts,
    domain_search,
    domains,
    export,
    health,
    jobs,
    lists,
    people,
    resolve,
    verify,
)

api_router = APIRouter(prefix="/v1")
api_router.include_router(health.router)
api_router.include_router(capture.router)
api_router.include_router(resolve.router)
api_router.include_router(contacts.router)
api_router.include_router(verify.router)
api_router.include_router(people.router)
api_router.include_router(companies.router)
api_router.include_router(domains.router)
api_router.include_router(lists.router)
# Week 4
api_router.include_router(jobs.router)
api_router.include_router(bulk.router)
# Week 7
api_router.include_router(domain_search.router)
# Week 8
api_router.include_router(export.router)

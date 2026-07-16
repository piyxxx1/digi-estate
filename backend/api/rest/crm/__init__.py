from fastapi import APIRouter
from .properties import router as properties_router
from .calls import router as calls_router
from .leads import router as leads_router
from .users import router as users_router
from .auth.auth import router as auth_router

router = APIRouter()

# Include subrouters to organize endpoints modularly
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(properties_router)
router.include_router(calls_router)
router.include_router(leads_router)
router.include_router(users_router)

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.settings import router as settings_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(stats_router)
api_router.include_router(settings_router)
api_router.include_router(health_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(documents_router)
api_router.include_router(sessions_router)
api_router.include_router(chat_router)

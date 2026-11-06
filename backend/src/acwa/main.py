from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from acwa.api.deps import password_is_valid, require_access
from acwa.api.routes import router
from acwa.clock import SystemClock
from acwa.config import Settings, get_settings
from acwa.db import get_engine, get_session_factory
from acwa.errors import ApiError
from acwa.integrations.deepseek import DeepSeekClient
from acwa.integrations.demo import DemoGenerator, DemoThreads
from acwa.integrations.threads import ThreadsClient
from acwa.logging_config import setup_logging
from acwa.security.crypto import TokenCipher
from acwa.seed import seed_demo


def build_generator(settings: Settings) -> DemoGenerator | DeepSeekClient:
    if settings.integration_mode == "demo":
        return DemoGenerator()
    return DeepSeekClient(settings)


def build_threads(settings: Settings) -> DemoThreads | ThreadsClient:
    if settings.integration_mode == "demo":
        return DemoThreads()
    return ThreadsClient(settings)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(app.state.settings.log_level)
        if app.state.settings.integration_mode == "demo" and app.state.settings.demo_seed:
            session = app.state.session_factory()
            try:
                seed_demo(session, app.state.clock, app.state.cipher)
                session.commit()
            finally:
                session.close()
        yield

    app = FastAPI(
        title="Account Warm-up",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.clock = SystemClock()
    app.state.cipher = TokenCipher(settings.token_encryption_key)
    app.state.generator = build_generator(settings)
    app.state.threads = build_threads(settings)
    get_engine(settings)
    app.state.session_factory = get_session_factory()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router, dependencies=[Depends(require_access)])

    @app.middleware("http")
    async def protect_unversioned_routes(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in {"/docs", "/redoc", "/openapi.json"} and not password_is_valid(
            request.headers.get("authorization"),
            request.app.state.settings.auth_token,
        ):
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "unauthorized", "message": "Нужен пароль приложения", "fields": {}}},
            )
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message, "fields": exc.fields}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for error in exc.errors():
            location = [str(item) for item in error["loc"] if item not in {"body", "query", "path"}]
            fields[".".join(location) or "body"] = "Проверьте значение поля"
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Проверьте поля запроса",
                    "fields": fields,
                }
            },
        )

    return app


app = create_app()

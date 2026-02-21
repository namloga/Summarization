import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException

from .routes import ErrorDetail, ErrorResponse, router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="API суммаризации отзывов",
    description="Сводка по отзывам: объединение всех отзывов из CSV/JSON в один текст и суммаризация в одну сводку.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        err = ErrorResponse(success=False, error=ErrorDetail(**detail))
    else:
        err = ErrorResponse(
            success=False,
            error=ErrorDetail(
                code="HTTP_ERROR",
                message=str(detail) if detail else "Ошибка запроса",
                detail=None,
            ),
        )
    return JSONResponse(status_code=exc.status_code, content=err.model_dump())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Необработанное исключение: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="Системная ошибка. Пожалуйста, попробуйте позже.",
                detail=str(exc),
            ),
        ).model_dump(),
    )


app.include_router(router, prefix="", tags=["summarization"])


@app.get("/")
def root():
    return {
        "service": "API суммаризации",
        "docs": "/docs",
        "health": "/health",
        "endpoints": ["POST /summarize", "POST /summarize-file", "GET /health"],
    }
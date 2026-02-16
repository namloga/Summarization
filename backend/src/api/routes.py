import io
import logging
import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

def _env_int(name: str, default: int, min_val: int, max_val: int) -> int:
    try:
        return max(min_val, min(int(os.getenv(name, str(default)).strip()), max_val))
    except ValueError:
        return default


MAX_FILE_ITEMS = _env_int("SUMMARIZATION_MAX_FILE_ITEMS", 2000, 1, 20_000)

class SummarizeRequest(BaseModel):
    text: str | None = Field(None, description="Текст для суммаризации")
    texts: list[str] | None = Field(None, description="Список текстов (если задан — приоритетнее)")

    def get_texts(self) -> list[str]:
        if self.texts:
            return [t for t in self.texts if t and str(t).strip()]
        if self.text and str(self.text).strip():
            return [str(self.text).strip()]
        return []


class SummarizeItemResponse(BaseModel):
    summary: str = Field(..., description="Сводка")
    original_length: int | None = Field(None, description="Длина исходного текста в символах (если есть)")


class SummarizeResponse(BaseModel):
    success: bool = True
    summaries: list[SummarizeItemResponse] = Field(..., description="Список результатов суммаризации")
    count: int = Field(..., description="Количество сводок")


class SummarizeFileStats(BaseModel):
    total_rows: int = Field(..., description="Общее число строк/записей в файле")
    extracted_texts: int = Field(..., description="Сколько текстов извлечено (после очистки)")
    summarized: int = Field(..., description="Сколько сводок создано")
    skipped: int = Field(0, description="Сколько пропущено (пустые/ошибка)")


class SummarizeFileResponse(BaseModel):
    success: bool = True
    summaries: list[SummarizeItemResponse] = Field(..., description="Список сводок по порядку")
    stats: SummarizeFileStats = Field(..., description="Статистика")
    filename: str | None = Field(None, description="Имя загруженного файла (если есть)")


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "summarization-api"
    version: str | None = None


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение для пользователя")
    detail: Any = Field(None, description="Технические детали (опционально)")


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail = Field(..., description="Данные об ошибке")


def _get_pipeline():
    from src.summarizer.pipeline import get_pipeline
    return get_pipeline()


@router.get("/health", response_model=HealthResponse)
def health():
    """Проверка доступности сервиса."""
    return HealthResponse(status="ok", service="summarization-api", version="1.0.0")


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(body: SummarizeRequest):
    """Принимает текст или список текстов и возвращает список сводок."""
    texts = body.get_texts()
    if not texts:
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(
                code = "EMPTY_INPUT",
                message = "Нужно передать 'text' или 'texts' (не пустые).",
                detail = None,
            ).model_dump(),
        )
    try:
        pipeline = _get_pipeline()
        summaries = pipeline.summarize_batch(texts, do_chunk=True)
        items = [
            SummarizeItemResponse(summary=s, original_length=len(t) if t else 0)
            for t, s in zip(texts, summaries)
        ]
        return SummarizeResponse(success=True, summaries=items, count=len(items))
    except Exception as e:
        logger.exception("Ошибка суммаризации: %s", e)
        raise HTTPException(
            status_code = 500,
            detail = ErrorDetail(
                code = "SUMMARIZATION_ERROR",
                message = "Ошибка при суммаризации. Пожалуйста, попробуйте ещё раз.",
                detail = str(e),
            ).model_dump(),
        )


@router.post("/summarize-file", response_model=SummarizeFileResponse)
async def summarize_file(
    file: UploadFile = File(..., description="CSV или JSON файл"),
    combine: bool = Query(True, description="Объединить все отзывы и сделать одну сводку"),
    detail: bool = Query(True, description="True: более подробно; False: короткая сводка"),
):
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in (".csv", ".json", ".jsonl"):
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(
                code = "UNSUPPORTED_FORMAT",
                message = "Поддерживаются только файлы .csv или .json",
                detail = {"filename": filename},
            ).model_dump(),
        )

    try:
        content = await file.read()
    except Exception as e:
        logger.exception("Ошибка чтения файла: %s", e)
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(
                code = "FILE_READ_ERROR",
                message = "Не удалось прочитать файл.",
                detail = str(e),
            ).model_dump(),
        )

    if not content:
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(code="EMPTY_FILE", message="Пустой файл.", detail=None).model_dump(),
        )

    try:
        from src.preprocessing.loaders import extract_texts_from_file

        buffer = io.BytesIO(content)
        texts = extract_texts_from_file(
            buffer,
            filename = filename,
            max_rows = MAX_FILE_ITEMS,
        )
    except ValueError as e:
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(
                code = "INVALID_FILE",
                message = str(e),
                detail = None,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Ошибка разбора файла: %s", e)
        raise HTTPException(
            status_code = 400,
            detail = ErrorDetail(
                code = "PARSE_ERROR",
                message = "Неверный формат файла или отсутствует колонка text/content/review.",
                detail = str(e),
            ).model_dump(),
        )

    total_extracted = len(texts)
    if total_extracted == 0:
        return SummarizeFileResponse(
            success = True,
            summaries = [],
            stats = SummarizeFileStats(
                total_rows = 0,
                extracted_texts = 0,
                summarized = 0,
                skipped = 0,
            ),
            filename = filename,
        )

    try:
        pipeline = _get_pipeline()
        if combine:
            combined = "\n\n".join(texts)
            logger.info("summarize-file: combine=True, detail=%s, n=%d", detail, total_extracted)
            summary = pipeline.summarize_one(combined, do_chunk=True, do_final_summarize=not detail)
            items = [
                SummarizeItemResponse(summary=summary, original_length=len(combined))
            ]
            return SummarizeFileResponse(
                success = True,
                summaries = items,
                stats = SummarizeFileStats(
                    total_rows = total_extracted,
                    extracted_texts = total_extracted,
                    summarized = 1 if summary else 0,
                    skipped = 0,
                ),
                filename=filename,
            )
        summaries = pipeline.summarize_batch(texts, do_chunk=True)
        items = [
            SummarizeItemResponse(summary=s, original_length=len(t))
            for t, s in zip(texts, summaries)
        ]
        return SummarizeFileResponse(
            success = True,
            summaries = items,
            stats = SummarizeFileStats(
                total_rows = total_extracted,
                extracted_texts = total_extracted,
                summarized = len([s for s in summaries if s]),
                skipped = sum(1 for s in summaries if not s),
            ),
            filename = filename,
        )
    except Exception as e:
        logger.exception("Ошибка суммаризации файла: %s", e)
        raise HTTPException(
            status_code = 500,
            detail = ErrorDetail(
                code = "SUMMARIZATION_ERROR",
                message = "Ошибка при суммаризации содержимого файла.",
                detail = str(e),
            ).model_dump(),
        )

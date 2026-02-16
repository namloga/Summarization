import csv
import io
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEXT_COLUMN_ALIASES = ("text", "content", "review", "feedback", "comment", "original_text")


def normalize_encoding(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return unicodedata.normalize("NFC", s.strip())


def clean_text(text: str, max_length: int | None = None) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    s = normalize_encoding(text)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    if max_length and len(s) > max_length:
        s = s[:max_length].rsplit(maxsplit=1)[0] if s.count(" ") else s[:max_length]
    return s

def _parse_max_file_mb() -> int:
    try:
        v = os.getenv("SUMMARIZATION_MAX_FILE_MB", "10").strip()
        n = int(v)
        return max(1, min(n, 100))
    except ValueError:
        return 10

MAX_FILE_SIZE_BYTES = _parse_max_file_mb() * 1024 * 1024

def detect_text_column(headers: list[str]) -> str | None:
    headers_lower = [h.strip().lower() for h in headers if h]
    for alias in TEXT_COLUMN_ALIASES:
        if alias in headers_lower:
            idx = headers_lower.index(alias)
            return headers[idx].strip()
    return None

def load_csv_texts(
    file_path: str | Path | io.BytesIO,
    text_column: str | None = None,
    encoding: str = "utf-8",
    max_rows: int | None = None,
) -> list[str]:
    if isinstance(file_path, (str, Path)):
        path = Path(file_path)
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл слишком большой (макс. {MAX_FILE_SIZE_BYTES // (1024*1024)} MB)")
        with open(path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.DictReader(f)
            return _extract_texts_from_csv_reader(reader, text_column, max_rows)
    content = file_path.getvalue()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Файл слишком большой (макс. {MAX_FILE_SIZE_BYTES // (1024*1024)} MB)")
    text_io = io.StringIO(content.decode(encoding, errors="replace"))
    reader = csv.DictReader(text_io)
    return _extract_texts_from_csv_reader(reader, text_column, max_rows)


def _extract_texts_from_csv_reader(
    reader: csv.DictReader,
    text_column: str | None,
    max_rows: int | None,
) -> list[str]:
    if not reader.fieldnames:
        return []
    col = text_column or detect_text_column(reader.fieldnames)
    if not col:
        raise ValueError(
            f"Не найдена колонка с текстом. Поддерживаемые имена: {', '.join(TEXT_COLUMN_ALIASES)}"
        )
    texts = []
    for row in reader:
        if max_rows and len(texts) >= max_rows:
            break
        raw = row.get(col) or ""
        t = clean_text(raw)
        if t:
            texts.append(t)
    return texts


def load_json_texts(
    file_path: str | Path | io.BytesIO,
    text_column: str | None = None,
    encoding: str = "utf-8",
    max_items: int | None = None,
) -> list[str]:
    if isinstance(file_path, (str, Path)):
        path = Path(file_path)
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл слишком большой (макс. {MAX_FILE_SIZE_BYTES // (1024*1024)} MB)")
        with open(path, "r", encoding=encoding, errors="replace") as f:
            data = json.load(f)
    else:
        content = file_path.getvalue()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл слишком большой (макс. {MAX_FILE_SIZE_BYTES // (1024*1024)} MB)")
        data = json.loads(content.decode(encoding, errors="replace"))

    items = _normalize_json_to_list(data)
    return _extract_texts_from_json_items(items, text_column, max_items)


def _normalize_json_to_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "items" in data:
            return data["items"] if isinstance(data["items"], list) else []
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
    return []


def _extract_texts_from_json_items(
    items: list[dict],
    text_column: str | None,
    max_items: int | None,
) -> list[str]:
    texts = []
    aliases = set(a.lower() for a in TEXT_COLUMN_ALIASES)
    for obj in items:
        if max_items and len(texts) >= max_items:
            break
        if not isinstance(obj, dict):
            continue
        raw = None
        if text_column and text_column in obj:
            raw = obj[text_column]
        else:
            for k, v in obj.items():
                if k and k.strip().lower() in aliases and v is not None:
                    raw = v
                    break
        if raw is None:
            continue
        t = clean_text(str(raw))
        if t:
            texts.append(t)
    return texts


def extract_texts_from_file(
    file_path: str | Path | io.BytesIO,
    filename: str | None = None,
    text_column: str | None = None,
    max_rows: int | None = None,
) -> list[str]:
    name = filename
    if name is None and hasattr(file_path, "name"):
        name = getattr(file_path, "name", "")
    if name is None and isinstance(file_path, Path):
        name = file_path.name
    if not name:
        name = ""

    ext = Path(name).suffix.lower()
    if ext == ".csv":
        return load_csv_texts(file_path, text_column=text_column, max_rows=max_rows)
    if ext in (".json", ".jsonl"):
        if ext == ".jsonl":
            return _load_jsonl_texts(file_path, text_column=text_column, max_items=max_rows)
        return load_json_texts(file_path, text_column=text_column, max_items=max_rows)
    raise ValueError("Неподдерживаемый формат файла. Используйте .csv или .json")


def _load_jsonl_texts(
    file_path: str | Path | io.BytesIO,
    text_column: str | None = None,
    max_items: int | None = None,
) -> list[str]:
    items = []
    if isinstance(file_path, io.BytesIO):
        for line in file_path.getvalue().decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return _extract_texts_from_json_items(items, text_column, max_items)

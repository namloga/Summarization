"""
Тесты pipeline: короткий текст возвращается как есть, dedupe убирает повторы.
Модель не загружается (короткий путь не вызывает модель).
"""

import pytest

# Короткий пример (≤250 символов) — должен вернуться без изменений
SHORT_RUSSIAN = "Сервис быстрый, товар пришёл в срок. Упаковка хорошая. Рекомендую продавца."


def test_short_text_returns_unchanged():
    """Вход ≤250 символов: summarize_one возвращает исходник, не вызывая модель."""
    from src.summarizer.pipeline import get_pipeline

    pipeline = get_pipeline()
    result = pipeline.summarize_one(SHORT_RUSSIAN, do_chunk=True)
    assert result == SHORT_RUSSIAN
    assert len(result) <= 250


def test_short_text_under_250_chars():
    """Текст ровно 250 символов тоже возвращается без изменений."""
    from src.summarizer.pipeline import get_pipeline

    pipeline = get_pipeline()
    text = "A" * 250
    result = pipeline.summarize_one(text, do_chunk=True)
    assert result == text


def test_dedupe_removes_duplicate_clauses():
    """_dedupe_summary убирает повторяющиеся клаузы (упаковка хорошая, упаковка хорошая → один раз)."""
    from src.summarizer.pipeline import get_pipeline

    pipeline = get_pipeline()
    summary = "Сервис быстрый, упаковка хорошая, упаковка хорошая. Рекомендую."
    out = pipeline._dedupe_summary(summary)
    assert "упаковка хорошая" in out
    assert out.count("упаковка хорошая") == 1


def test_dedupe_removes_x_and_x():
    """_dedupe_summary bỏ lặp dạng 'быстро и быстро' → 'быстро'."""
    from src.summarizer.pipeline import get_pipeline

    pipeline = get_pipeline()
    summary = "Продавец быстро и быстро доставил товар."
    out = pipeline._dedupe_summary(summary)
    assert "быстро и быстро" not in out
    assert "быстро" in out


def test_dedupe_short_string_unchanged():
    """Слишком короткая строка (<10 символов) остаётся без изменений."""
    from src.summarizer.pipeline import get_pipeline

    pipeline = get_pipeline()
    assert pipeline._dedupe_summary("Hi") == "Hi"
    assert pipeline._dedupe_summary("") == ""

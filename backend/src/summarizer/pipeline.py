"""
Pipeline суммаризации: ruT5/T5, chunking для длинного текста, постобработка (dedupe, границы предложений).
"""

import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_MAX_INPUT_LENGTH = 512
DEFAULT_MAX_OUTPUT_LENGTH = 160
DEFAULT_MAX_SOURCE_LENGTH_CHARS = 1500
DEFAULT_MODEL_NAME = os.getenv("SUMMARIZATION_MODEL", "IlyaGusev/rut5_base_sum_gazeta")

# Единый экземпляр pipeline (ленивая загрузка)
_pipeline: "SummarizerPipeline | None" = None


def get_pipeline(
    model_name: str | None = None,
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
    max_output_length: int = DEFAULT_MAX_OUTPUT_LENGTH,
    force_reload: bool = False,
) -> "SummarizerPipeline":
    global _pipeline
    if _pipeline is not None and not force_reload:
        return _pipeline
    _pipeline = SummarizerPipeline(
        model_name=model_name or DEFAULT_MODEL_NAME,
        max_input_length=max_input_length,
        max_output_length=max_output_length,
    )
    return _pipeline


class SummarizerPipeline:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
        max_output_length: int = DEFAULT_MAX_OUTPUT_LENGTH,
        max_source_length_chars: int = DEFAULT_MAX_SOURCE_LENGTH_CHARS,
    ):
        self.model_name = model_name
        self.max_input_length = max_input_length
        self.max_output_length = max_output_length
        self.max_source_length_chars = max_source_length_chars
        self._model = None
        self._tokenizer = None

    def load(self) -> None:
        """Ленивая загрузка модели и токенайзера с Hugging Face."""
        if self._model is not None:
            return
        try:
            from transformers import AutoTokenizer, T5ForConditionalGeneration
        except ImportError as e:
            raise ImportError(
                "Требуется установить зависимости: pip install transformers torch"
            ) from e

        logger.info("Загрузка модели %s...", self.model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = T5ForConditionalGeneration.from_pretrained(self.model_name)
        self._model.eval()
        logger.info("Модель загружена.")

    @property
    def model(self):
        self.load()
        return self._model

    @property
    def tokenizer(self):
        self.load()
        return self._tokenizer

    def _chunk_by_paragraphs(self, text: str) -> List[str]:
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        if not blocks:
            return []
        n = len(blocks)
        limit = 700 if n >= 6 else (1000 if n >= 4 else self.max_source_length_chars)
        max_chars = min(self.max_source_length_chars, limit)
        chunks = []
        current = ""
        for block in blocks:
            if len(block) > max_chars:
                sub = self._chunk_sentences(block)
                for s in sub:
                    chunks.append(s)
                current = ""
                continue
            candidate = (current + "\n\n" + block).strip() if current else block
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = block
        if current:
            chunks.append(current)
        return chunks

    def _chunk_sentences(self, text: str) -> List[str]:
        if len(text) <= self.max_source_length_chars:
            return [text] if text.strip() else []
        chunks = []
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        current = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(current) + len(s) + 1 <= self.max_source_length_chars:
                current = (current + ". " + s).strip() if current else s
            else:
                if current:
                    chunks.append(current)
                current = s[: self.max_source_length_chars]
                if len(s) > self.max_source_length_chars:
                    part = s[: self.max_source_length_chars].rsplit(maxsplit=1)[0]
                    chunks.append(part)
                    current = s[len(part) :].strip()
                else:
                    current = s
        if current:
            chunks.append(current)
        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self.max_source_length_chars:
            return [text] if text.strip() else []
        if "\n\n" in text:
            return self._chunk_by_paragraphs(text)
        return self._chunk_sentences(text)

    def _dedupe_sentences_light(self, text: str) -> str:
        """Удаляет полностью повторяющиеся предложения, сохраняя остальное (режим detail)."""
        if not text or len(text) < 10:
            return text.strip()
        parts = [p.strip() for p in text.split(".") if p.strip()]
        seen: set[str] = set()
        out: List[str] = []
        for p in parts:
            key = p.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        s = ". ".join(out).strip()
        return s if not s or s.endswith(".") else s + "."

    def _fix_sentence_boundaries(self, text: str) -> str:
        if not text or len(text) < 10:
            return text.strip()
        s = text.strip()
        for pattern, repl in [
            (r"\.\s+потому что\b", ", потому что"),
            (r"\.\s+поэтому\b", ", поэтому"),
            (r"\.\s+но\s+", ", но "),
            (r"\.\s+что\s+", ", что "),
            (r"\.\s+и\s+", ", и "),
        ]:
            s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
        return s

    def _dedupe_summary(self, summary: str) -> str:
        """Удаляет повторяющиеся фразы/клаузы (для короткой сводки или chunk-режима)."""
        if not summary or len(summary) < 10:
            return summary.strip()
        summary = re.sub(r"\b(\w+)\s+и\s+\1\b", r"\1", summary, flags=re.IGNORECASE)
        clauses = re.split(r"[.,]", summary)
        seen = set()
        out = []
        for c in clauses:
            c = re.sub(r"\s+", " ", c).strip()
            if not c or len(c) < 2:
                continue
            m_tail = re.search(r"\s+и\s+(\w+)\s*$", c, re.IGNORECASE)
            if m_tail:
                word_at_end = m_tail.group(1).lower()
                rest = c[: m_tail.start()].lower()
                if re.search(r"\b" + re.escape(word_at_end) + r"\b", rest):
                    c = c[: m_tail.start()].strip()
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        if not out:
            return summary.strip()
        return ". ".join(out).strip()

    def summarize_one(
        self,
        text: str,
        do_chunk: bool = True,
        do_final_summarize: bool = False,
    ) -> str:
        if not text or not text.strip():
            return ""
        text = text.strip()
        if len(text) <= 250:
            return text

        if do_chunk and len(text) > self.max_source_length_chars:
            chunks = self._chunk_text(text)
            logger.debug("summarize_one: len=%d, chunks=%d", len(text), len(chunks))
            summaries = [s for ch in chunks if ch.strip() for s in [self._summarize_single(ch)] if s]
            if not summaries:
                return ""
            normalized = []
            for s in summaries:
                s = s.strip()
                if not s:
                    continue
                normalized.append(s if s[-1] in ".!?" else s + ".")
            combined = " ".join(normalized).strip()
            combined = self._dedupe_summary(combined) if do_final_summarize else self._dedupe_sentences_light(combined)
            if (
                do_final_summarize
                and len(normalized) >= 2
                and 300 < len(combined) <= self.max_source_length_chars
            ):
                return self._summarize_single(combined)
            return self._fix_sentence_boundaries(combined)

        return self._summarize_single(text)

    def _summarize_single(self, text: str) -> str:
        import torch

        self.load()
        text_len = len(text.strip())
        if text_len < 300:
            max_out = min(50, self.max_output_length)
            min_out = 5
        else:
            max_out = self.max_output_length
            min_out = 10

        inputs = self.tokenizer(
            text,
            max_length=self.max_input_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = inputs["input_ids"]
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_length=max_out,
                min_length=min_out,
                no_repeat_ngram_size=3,
                repetition_penalty=2.5,
                num_beams=4,
                early_stopping=True,
            )
        summary = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        summary = summary.strip()
        summary = self._dedupe_summary(summary)
        if len(summary) > len(text):
            summary = self._dedupe_summary(text)
        return self._fix_sentence_boundaries(summary)

    def summarize_batch(self, texts: List[str], do_chunk: bool = True) -> List[str]:
        result = []
        for t in texts:
            if not t or not str(t).strip():
                result.append("")
                continue
            result.append(self.summarize_one(str(t).strip(), do_chunk=do_chunk))
        return result
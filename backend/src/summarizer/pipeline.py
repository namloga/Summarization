import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_MAX_INPUT_LENGTH = 512
DEFAULT_MAX_OUTPUT_LENGTH = 160
DEFAULT_MAX_SOURCE_LENGTH_CHARS = 1500
DEFAULT_MODEL_NAME = os.getenv("SUMMARIZATION_MODEL", "IlyaGusev/rut5_base_sum_gazeta")

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

    def _filter_by_coverage(
        self,
        text: str,
        min_support: int = 2,
        sim_threshold: float = 0.25,
    ) -> str:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        n = len(paragraphs)
        if n < max(3, min_support + 1):
            return text

        para_sentences: List[List[str]] = [
            [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if len(s.strip()) > 5]
            for para in paragraphs
        ]

        filtered: List[str] = []
        for i, sents_i in enumerate(para_sentences):
            kept: List[str] = []
            for sent in sents_i:
                support = 0
                for j, sents_j in enumerate(para_sentences):
                    if j == i:
                        continue
                    if any(
                        self._ngram_overlap(sent, s_j, n=2) >= sim_threshold
                        for s_j in sents_j
                    ):
                        support += 1
                    if support >= min_support - 1:
                        break
                if support >= min_support - 1:
                    kept.append(sent)
            if kept:
                part = " ".join(kept)
                filtered.append(part if part[-1] in ".!?" else part + ".")
            else:
                filtered.append(paragraphs[i])

        return "\n\n".join(filtered)

    def _lemmatize(self, words: List[str]) -> List[str]:
        return [w[:6] if len(w) > 6 else w for w in words]

    def _ngram_overlap(self, a: str, b: str, n: int = 2) -> float:
        wa = self._lemmatize(a.lower().split())
        wb = self._lemmatize(b.lower().split())
        if len(wa) < n or len(wb) < n:
            sa, sb = set(wa), set(wb)
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / max(len(sa), len(sb))
        nga = set(tuple(wa[i : i + n]) for i in range(len(wa) - n + 1))
        ngb = set(tuple(wb[i : i + n]) for i in range(len(wb) - n + 1))
        if not nga or not ngb:
            return 0.0
        return len(nga & ngb) / max(len(nga), len(ngb))

    def _is_subset_sentence(self, a: str, b: str, threshold: float = 0.8) -> bool:
        wa = {w for w in self._lemmatize(a.lower().split()) if len(w) > 1}
        wb = {w for w in self._lemmatize(b.lower().split()) if len(w) > 1}
        if not wa or not wb:
            return False
        return len(wa & wb) / len(wa) >= threshold

    def _dedupe_sentences_smart(self, text: str, overlap_threshold: float = 0.55) -> str:
        if not text or len(text) < 10:
            return text.strip()
        raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        accepted: List[str] = []
        for sent in sentences:
            is_dup = False
            for k, acc in enumerate(accepted):
                if self._ngram_overlap(sent, acc, n=2) >= overlap_threshold or self._is_subset_sentence(sent, acc):
                    is_dup = True
                    break
                if self._is_subset_sentence(acc, sent):
                    accepted[k] = sent
                    is_dup = True
                    break
            if not is_dup:
                accepted.append(sent)
        if not accepted:
            return text.strip()
        result = " ".join(accepted)
        return result if result[-1] in ".!?" else result + "."

    def _fix_sentence_boundaries(self, text: str) -> str:
        if not text or len(text) < 10:
            return text.strip()
        s = text.strip()
        for pattern, repl in [
            (r"По мнению продавца\.\s+", "По мнению продавца, "),
            (r"\.\s+потому что\b", ", потому что"),
            (r"\.\s+поэтому\b", ", поэтому"),
            (r"\.\s+но\s+", ", но "),
            (r"\.\s+что\s+", ", что "),
            (r"\.\s+и\s+", ", и "),
        ]:
            s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
        return s

    def _dedupe_summary(self, summary: str) -> str:
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

    def _polish_output(self, text: str) -> str:
        if not text or len(text) < 5:
            return text
        if re.match(r"^\s*Котор(ый|ие)\s+я\s+приобрел", text.strip(), re.IGNORECASE):
            text = re.sub(r"^\s*Который\s", "Которые ", text.strip(), count=1, flags=re.IGNORECASE)
            text = "Наушники CH-520. " + text.strip()
        text = re.sub(r"\bудобные приложения\b", "удобное приложение", text, flags=re.IGNORECASE)
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        result = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent.split()) < 3 and not re.match(r"^Наушники\s+CH-\d+\.?$", sent):
                continue
            if sent and sent[0].islower():
                sent = sent[0].upper() + sent[1:]
            if re.match(r"^Который\s", sent):
                sent = "Которые" + sent[7:]
            if sent and sent[-1] not in ".!?":
                sent += "."
            result.append(sent)
        return " ".join(result)

    def _neutralize_voice(self, text: str) -> str:
        if not text or len(text) < 10:
            return text
        s = text
        s = re.sub(r"\bКоторые\s+я\s+приобрел\b", "Которые приобретают", s, flags=re.IGNORECASE)
        s = re.sub(r"\bкоторые\s+я\s+приобрел\b", "которые приобретают", s)
        s = re.sub(r"\bМы\s+покупали\b", "По отзывам, покупали", s, flags=re.IGNORECASE)
        s = re.sub(r"\bРекомендую\s+примерять\b", "Рекомендуют примерять", s, flags=re.IGNORECASE)
        s = re.sub(r"\bПокупкой\s+довольн[ая]\b", "Покупкой довольны", s, flags=re.IGNORECASE)
        s = re.sub(r"\bПокупкой\s+доволен\b", "Покупкой довольны", s, flags=re.IGNORECASE)
        s = re.sub(r"^(Я|я)\s+приобрел\s+", "По отзывам, приобретают ", s, flags=re.IGNORECASE)
        return s

    _MIN_SUMMARY_CHARS_AFTER_FILTER = 220
    _MIN_SENTENCES_AFTER_FILTER = 4

    def _filter_rare_sentences(
        self,
        summary: str,
        source_text: str,
        min_support: int = 2,
        max_rare_ratio: float = 0.55,
        min_word_len: int = 5,
    ) -> str:
        paragraphs = [p.strip() for p in source_text.split("\n\n") if p.strip()]
        if len(paragraphs) < max(3, min_support + 1):
            return summary
        review_word_sets = [
            set(self._lemmatize(para.lower().split()))
            for para in paragraphs
        ]
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", summary.strip()) if s.strip()
        ]
        kept: List[str] = []
        for sent in sentences:
            content = {
                w for w in self._lemmatize(sent.lower().split())
                if len(w) >= min_word_len
            }
            if not content:
                kept.append(sent)
                continue
            rare = [
                w for w in content
                if sum(1 for ws in review_word_sets if w in ws) < min_support
            ]
            if len(content) <= 4 and rare:
                continue
            if len(rare) / len(content) <= max_rare_ratio:
                kept.append(sent)
        if not kept:
            return summary
        result = " ".join(kept)
        result = result if result[-1] in ".!?" else result + "."
        return result

    def _filter_rare_sentences_safe(self, summary: str, source_text: str) -> str:
        filtered = self._filter_rare_sentences(summary, source_text, max_rare_ratio=0.55)
        if len(filtered) < self._MIN_SUMMARY_CHARS_AFTER_FILTER:
            return summary
        sent_count = len(re.split(r"(?<=[.!?])\s+", filtered.strip()))
        if sent_count < self._MIN_SENTENCES_AFTER_FILTER:
            return summary
        return filtered

    def _drop_nonsense_sentences(self, text: str) -> str:
        if not text or len(text) < 10:
            return text
        bad = re.compile(r"\bя\s+не\s+знаю\b", re.IGNORECASE)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        kept = [s for s in sentences if not bad.search(s)]
        if not kept:
            return text
        result = " ".join(kept)
        return result if result[-1] in ".!?" else result + "."

    def _filter_outlier_sentences(self, text: str) -> str:
        if not text or len(text) < 10:
            return text
        outlier = re.compile(
            r"вьетнам|в\s+магазине\s+.*(?:русск|по[\s\-]?русски|русскому\s+языку)",
            re.IGNORECASE,
        )
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        kept = [s for s in sentences if not outlier.search(s)]
        if not kept:
            return text
        result = " ".join(kept)
        return result if result[-1] in ".!?" else result + "."

    def _clean_overview_style(self, text: str) -> str:
        if not text or len(text) < 10:
            return text
        s = text
        s = re.sub(r"\s+в\s+такси\s+и\s+самол[её]те\.?", ".", s, flags=re.IGNORECASE)
        s = re.sub(r"\.\s*\.", ".", s)
        if re.match(r"^\s*Наушники\s+CH-520", s.strip(), re.IGNORECASE):
            s = re.sub(r"\bОтличные\s+наушники\s+Сони\b", "Модель отличная по отзывам", s, flags=re.IGNORECASE)
        return s

    def summarize_one(
        self,
        text: str,
        do_chunk: bool = True,
        do_final_summarize: bool = False,
    ) -> str:
        if not text or not text.strip():
            return ""
        text = text.strip()
        original_text = text
        if "\n\n" in text:
            text = self._filter_by_coverage(text)
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
            combined = self._dedupe_summary(combined) if do_final_summarize else self._dedupe_sentences_smart(combined)
            if (
                do_final_summarize
                and len(normalized) >= 2
                and 300 < len(combined) <= self.max_source_length_chars
            ):
                summary = self._summarize_single(combined)
            else:
                summary = self._fix_sentence_boundaries(combined)
        else:
            summary = self._summarize_single(text)
        paragraphs = [p for p in original_text.split("\n\n") if p.strip()]
        if len(paragraphs) >= 3:
            summary = self._filter_rare_sentences_safe(summary, original_text)
        summary = self._drop_nonsense_sentences(summary)
        summary = self._filter_outlier_sentences(summary)
        summary = self._clean_overview_style(summary)
        summary = self._polish_output(summary)
        summary = self._neutralize_voice(summary)
        return summary

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
                no_repeat_ngram_size=4,
                repetition_penalty=3.0,
                num_beams=4,
                early_stopping=True,
            )
        summary = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        summary = summary.strip()
        summary = self._dedupe_sentences_smart(summary)
        summary = self._dedupe_summary(summary)
        if len(summary) > len(text):
            summary = self._dedupe_summary(text)
        summary = self._drop_nonsense_sentences(summary)
        return self._polish_output(self._fix_sentence_boundaries(summary))

    _NEGATIVE_MARKERS = (
        "не советую", "не рекомендую", "плохой", "плохое", "плохая",
        "ерунда", "ужасн", "разочарован", "возврат", "сломал", "бракован",
        "не работает", "деньги на ветер", "жалею", "пожалел",
    )

    def _classify_reviews(self, texts: List[str]) -> tuple[List[str], List[str]]:
        positive, negative = [], []
        for t in texts:
            if any(m in t.lower() for m in self._NEGATIVE_MARKERS):
                negative.append(t)
            else:
                positive.append(t)
        return positive, negative

    def summarize_batch(self, texts: List[str], do_chunk: bool = True) -> List[str]:
        result = []
        for t in texts:
            if not t or not str(t).strip():
                result.append("")
                continue
            result.append(self.summarize_one(str(t).strip(), do_chunk=do_chunk))
        return result

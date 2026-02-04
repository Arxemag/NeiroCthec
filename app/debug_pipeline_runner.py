from pathlib import Path

from core.pipeline.stage0_format_detector import FormatDetector
from core.pipeline.stage0_format_parser import FormatParser
from core.pipeline.stage0_text_extractor import TextExtractor

from core.pipeline.stage1_1_chapter_parser import ChapterParser
from core.pipeline.stage1_2_line_type_parser import LineTypeParser
from core.pipeline.stage1_3_segment_analyzer import SegmentAnalyzer
from core.pipeline.stage1_4_segment_text_adapter import SegmentTextAdapter
from core.pipeline.stage1_5_stress_placeholder import StressPlaceholder


def print_block(title: str):
    print("\n" + title)
    print("-" * len(title))


def preview(title: str, items, formatter, limit=5):
    print_block(title)
    for i, item in enumerate(items[:limit]):
        print(f"{i+1:02d}. {formatter(item)}")
    if len(items) > limit:
        print(f"... ({len(items) - limit} more)")


def debug_run(book_path: str):
    print("=" * 80)
    print(f"📘 DEBUG PIPELINE RUN: {book_path}")
    print("=" * 80)

    path = Path(book_path)

    # ---------- Stage 0.1 ----------
    print("\n🟦 Stage 0.1 — FormatDetector")
    fmt = FormatDetector().detect(path)
    print(f"Формат: {fmt}")

    # ---------- Stage 0.2 ----------
    print("\n🟦 Stage 0.2 — FormatParser")
    raw_text = FormatParser().parse(path, fmt)
    print(f"Raw size: {len(raw_text)} chars")

    # ---------- Stage 0.3 ----------
    print("\n🟦 Stage 0.3 — TextExtractor")
    normalized = TextExtractor().extract(raw_text, fmt)

    preview(
        "Извлечённые строки:",
        normalized.lines,
        lambda l: l[:120]
    )

    # ---------- Stage 1.1 ----------
    print("\n🟦 Stage 1.1 — ChapterParser")
    chapters = ChapterParser().parse(normalized)

    preview(
        "Главы:",
        chapters,
        lambda c: f"Chapter {c.index}: title={c.title!r}, lines={len(c.lines)}"
    )

    # ---------- Stage 1.2 ----------
    print("\n🟦 Stage 1.2 — LineTypeParser")
    lines = LineTypeParser().parse(chapters)

    preview(
        "Lines:",
        lines,
        lambda l: f"[{l.type}] {l.original[:120]}"
    )

    # ---------- Stage 1.3 ----------
    print("\n🟦 Stage 1.3 — SegmentAnalyzer")
    analyzer = SegmentAnalyzer()
    all_segments = []

    for line in lines:
        segs = analyzer.split(line)
        all_segments.extend(segs)

        # Жёсткий инвариант
        joined = "".join(s.original_text for s in segs)
        if joined != line.original:
            raise RuntimeError(
                f"❌ Segment invariant broken\n"
                f"ORIGINAL: {line.original!r}\n"
                f"JOINED  : {joined!r}"
            )

    preview(
        "Segments (original_text):",
        all_segments,
        lambda s: f"[L{s.line_id}:{s.kind}] {s.original_text!r}"
    )

    # ---------- Stage 1.4 ----------
    print("\n🟦 Stage 1.4 — SegmentTextAdapter")
    adapter = SegmentTextAdapter()
    for i, seg in enumerate(all_segments):
        adapter.adapt(seg, is_last=(i == len(all_segments) - 1))

    preview(
        "Segments (tts_text):",
        all_segments,
        lambda s: f"[L{s.line_id}:{s.kind}] {s.tts_text!r}"
    )

    # ---------- Stage 1.5 ----------
    print("\n🟦 Stage 1.5 — StressPlaceholder")
    stress = StressPlaceholder()
    for seg in all_segments:
        stress.apply(seg)

    preview(
        "Stress maps:",
        all_segments,
        lambda s: f"[L{s.line_id}] stress_map={s.stress_map}"
    )

    print("\n✅ PIPELINE FINISHED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    debug_run("book.txt")
    debug_run("book.fb2")

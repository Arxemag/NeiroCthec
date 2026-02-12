from pathlib import Path
from datetime import datetime

from core.pipeline.stage0_format_detector import FormatDetector
from core.pipeline.stage0_format_parser import FormatParser
from core.pipeline.stage0_text_extractor import TextExtractor
from core.pipeline.stage1_1_chapter_parser import ChapterParser
from core.pipeline.stage1_2_line_type_parser import LineTypeParser

from core.pipeline.stage1_3_segment_analyzer import SegmentAnalyzer
from core.pipeline.stage1_4_segment_text_adapter import SegmentTextAdapter
from core.pipeline.stage1_5_stress import StressPlaceholder


# =========================
# Utils
# =========================

def save(name: str, content: str):
    out = Path("debug_output")
    out.mkdir(exist_ok=True)
    path = out / name
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"💾 saved: {path}")


def line_sep(title: str):
    return f"\n{'=' * 20} {title} {'=' * 20}\n"


# =========================
# MAIN DEBUG
# =========================

def debug_stage1_5(book_path: str, limit_lines: int = 50):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    book_path = Path(book_path)
    book_name = book_path.stem

    print("=" * 80)
    print("🎯 DEBUG Stage 1.5 — REAL TRACE")
    print("=" * 80)

    # ---------- Pipeline до сегментов ----------

    fmt = FormatDetector().detect(book_path)
    raw = FormatParser().parse(book_path, fmt)
    normalized = TextExtractor().extract(raw, fmt)

    chapters = ChapterParser().parse(normalized)
    lines = LineTypeParser().parse(chapters)
    lines = lines[:limit_lines]

    analyzer = SegmentAnalyzer()
    adapter = SegmentTextAdapter()
    stress = StressPlaceholder()

    segments = []

    for line in lines:
        segs = analyzer.split(line)
        for seg in segs:
            adapter.adapt(seg, is_last=False)
            segments.append(seg)

    # ---------- TRACE BEFORE ----------

    before = []
    for i, seg in enumerate(segments):
        before.append(
            f"[#{i}] L{seg.line_id}:{seg.kind}\n"
            f"ORIGINAL_TEXT: {repr(seg.original_text)}\n"
            f"TTS_TEXT     : {repr(seg.tts_text)}\n"
            f"{'-' * 60}"
        )

    save(
        f"{ts}_{book_name}_01_BEFORE.txt",
        "\n".join(before)
    )

    # ---------- APPLY STRESS ----------

    applied = 0
    skipped_empty = 0
    skipped_no_dict = 0

    for seg in segments:
        before_text = seg.tts_text or seg.original_text
        stress.apply(seg)

        if not before_text:
            skipped_empty += 1
        elif not seg.stress_map:
            skipped_no_dict += 1
        else:
            applied += 1

    # ---------- TRACE AFTER + REASONS ----------

    after = []
    diff = []

    for i, seg in enumerate(segments):
        src = seg.original_text
        tts = seg.tts_text or src

        after.append(
            f"[#{i}] L{seg.line_id}:{seg.kind}\n"
            f"TTS_TEXT: {repr(tts)}\n"
            f"STRESS_MAP: {seg.stress_map}\n"
            f"{'-' * 60}"
        )

        if seg.stress_map:
            diff.append(
                f"[#{i}] L{seg.line_id}:{seg.kind}\n"
                f"ORIG: {src}\n"
                f"TTS : {tts}\n"
                f"MAP : {seg.stress_map}\n"
                f"{'=' * 60}"
            )

    save(
        f"{ts}_{book_name}_02_AFTER.txt",
        "\n".join(after)
    )

    save(
        f"{ts}_{book_name}_03_DIFF.txt",
        "\n".join(diff) if diff else "❌ Ударения не применены ни к одному сегменту"
    )

    # ---------- SUMMARY ----------

    summary = (
        f"STAGE 1.5 DEBUG SUMMARY\n"
        f"{'=' * 40}\n"
        f"Всего сегментов      : {len(segments)}\n"
        f"С ударениями         : {applied}\n"
        f"Пустой текст         : {skipped_empty}\n"
        f"Нет в словаре        : {skipped_no_dict}\n"
    )

    save(
        f"{ts}_{book_name}_00_SUMMARY.txt",
        summary
    )

    print("\n✅ DEBUG COMPLETE")
    print(summary)
    print("📁 debug_output/")


if __name__ == "__main__":
    debug_stage1_5("book.fb2", limit_lines=50)

from pathlib import Path

from core.pipeline.stage0_format_detector import FormatDetector
from core.pipeline.stage0_format_parser import FormatParser
from core.pipeline.stage0_text_extractor import TextExtractor
from core.pipeline.stage1_1_chapter_parser import ChapterParser
from core.pipeline.stage1_2_line_type_parser import LineTypeParser
from core.pipeline.stage1_3_segment_analyzer import SegmentAnalyzer
from core.pipeline.stage1_4_segment_text_adapter import SegmentTextAdapter
from core.pipeline.stage1_5_stress_placeholder import StressPlaceholder

from core.models import UserBookFormat, Remark, Line
from core.pipeline.stage2_speaker_resolver import SpeakerResolver, SpeakerResolverConfig


def print_block(title: str):
    print("\n" + title)
    print("-" * len(title))


def preview(title: str, items, formatter, limit=5):
    print_block(title)
    for i, item in enumerate(items[:limit]):
        print(f"{i + 1:02d}. {formatter(item)}")
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
    lines_from_stage1_2 = LineTypeParser().parse(chapters)

    preview(
        "Lines from Stage 1.2:",
        lines_from_stage1_2,
        lambda l: f"[{l.type}] {l.original[:120]}"
    )

    # 🔥 ---------- Stage 2 ----------
    print("\n🎭 Stage 2 — SpeakerResolver (ИСПРАВЛЕННАЯ ВЕРСИЯ)")
    print("🔥 Анализ на оригинальных линиях с правильными приоритетами")

    # Подготавливаем линии для Stage 2
    for i, line in enumerate(lines_from_stage1_2):
        line.idx = i
        if not hasattr(line, 'remarks') or line.remarks is None:
            line.remarks = []

    ubf = UserBookFormat(lines=lines_from_stage1_2)

    # Настраиваем резолвер с ВСТРОЕННЫМ дебагом
    config = SpeakerResolverConfig(
        confidence_threshold=1.0,
        high_confidence_threshold=1.8,
        use_narrator_fallback=False,
        debug_detailed=True  # 🔥 ВКЛЮЧАЕМ ВСТРОЕННЫЙ ДЕБАГ
    )

    resolver = SpeakerResolver(config)

    # 🔥 ПРОСТО ЗАПУСКАЕМ - новый резолвер сам выводит детали
    print("\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ СПИКЕРОВ (встроенный):")
    lines_with_speakers = resolver.process(ubf).lines

    # 🔥 АНАЛИЗ РЕЗУЛЬТАТОВ
    print_block("🏁 ИТОГОВЫЕ РЕЗУЛЬТАТЫ Stage 2")

    # Группируем строки по типам
    narrator_lines = [l for l in lines_with_speakers if l.type != "dialogue"]
    dialogue_lines = [l for l in lines_with_speakers if l.type == "dialogue"]

    print(f"📖 Narrator строк: {len(narrator_lines)}")
    print(f"💬 Dialogue строк: {len(dialogue_lines)}")

    # Анализ диалоговых строк
    print("\n🔍 АНАЛИЗ ДИАЛОГОВЫХ СТРОК:")
    male_verbs = ["спросил", "скомандовал", "выдохнул", "произнес"]
    female_verbs = ["доложила", "сообщила", "сказала"]

    correct_detections = 0
    incorrect_detections = 0
    problematic_lines = []

    for i, line in enumerate(dialogue_lines):
        text_lower = line.original.lower()
        expected_gender = None

        # Определяем ожидаемый пол по глаголам
        for verb in male_verbs:
            if verb in text_lower:
                expected_gender = "male"
                break

        for verb in female_verbs:
            if verb in text_lower:
                expected_gender = "female"
                break

        status = "✅"
        if expected_gender:
            if line.speaker == expected_gender:
                correct_detections += 1
                status = "✅"
            else:
                incorrect_detections += 1
                status = "❌"
                problematic_lines.append((i, line, expected_gender))
        else:
            status = "⚠️"  # Не можем проверить - нет явных глаголов

        print(f"{status} {i + 1:02d}. {line.speaker} | {text_lower[:80]}...")

    # Выводим проблемные строки
    if problematic_lines:
        print_block("❌ ПРОБЛЕМНЫЕ ОПРЕДЕЛЕНИЯ:")
        for idx, line, expected in problematic_lines:
            print(f"Line {idx}:")
            print(f"   Текст: {line.original[:100]}...")
            print(f"   Ожидался: {expected}")
            print(f"   Получено: {line.speaker}")

    # Статистика точности
    if correct_detections + incorrect_detections > 0:
        accuracy = (correct_detections / (correct_detections + incorrect_detections)) * 100
        print_block("📊 ТОЧНОСТЬ АЛГОРИТМА")
        print(f"Правильно: {correct_detections}")
        print(f"Неправильно: {incorrect_detections}")
        print(f"Точность: {accuracy:.1f}%")

    # Общая статистика
    print_block("📈 ОБЩАЯ СТАТИСТИКА")
    speaker_distribution = {}
    for line in lines_with_speakers:
        speaker = line.speaker if line.speaker else "unknown"
        speaker_distribution[speaker] = speaker_distribution.get(speaker, 0) + 1

    for speaker, count in speaker_distribution.items():
        percentage = (count / len(lines_with_speakers)) * 100
        print(f"{speaker}: {count} строк ({percentage:.1f}%)")

    # ---------- Stage 1.3 ----------
    print("\n🟦 Stage 1.3 — SegmentAnalyzer")

    # Передаем спикеров сегментам
    analyzer = SegmentAnalyzer()
    all_segments = []

    for line in lines_with_speakers:
        segs = analyzer.split(line)
        for seg in segs:
            seg.speaker = line.speaker  # Наследуем спикера
        all_segments.extend(segs)

        # Проверяем инвариант
        joined = "".join(s.original_text for s in segs)
        if joined != line.original:
            raise RuntimeError(f"❌ Segment invariant broken")

    preview(
        "Segments с спикерами:",
        all_segments,
        lambda s: f"[L{s.line_id}:{s.kind}] {s.speaker} | {s.original_text[:60]}..."
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

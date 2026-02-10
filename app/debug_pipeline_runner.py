from pathlib import Path
import json
from datetime import datetime

from core.pipeline.stage0_format_detector import FormatDetector
from core.pipeline.stage0_format_parser import FormatParser
from core.pipeline.stage0_text_extractor import TextExtractor
from core.pipeline.stage1_1_chapter_parser import ChapterParser
from core.pipeline.stage1_2_line_type_parser import LineTypeParser
from core.pipeline.stage1_3_segment_analyzer import SegmentAnalyzer
from core.pipeline.stage1_4_segment_text_adapter import SegmentTextAdapter
from core.pipeline.stage1_5_stress import StressPlaceholder

from core.models import UserBookFormat, Remark, Line
from core.pipeline.stage2_speaker_resolver import SpeakerResolver, SpeakerResolverConfig

# 🔥 ИМПОРТИРУЕМ НОВЫЙ СТЕЙДЖ
from core.pipeline.stage2_5_character_collector import run_character_collection

class TTSDirector:
    def apply(self, segment: Segment):
        text = segment.original_text.lower()

        meta = TTSMeta()

        # 🔊 ГРОМКОСТЬ
        if "прошептал" in text or "шепотом" in text:
            meta.volume = "whisper"
            meta.reason = "указание на шепот"

        elif "тихо сказал" in text or "сказал тихо" in text:
            meta.volume = "quiet"
            meta.reason = "указание на тихую речь"

        elif "закричал" in text or "воскликнул" in text:
            meta.volume = "loud"
            meta.emotion = "angry"
            meta.reason = "крик / восклицание"

        # 😡 ЭМОЦИИ
        if "злобно" in text:
            meta.emotion = "angry"
            meta.reason = "злобно"

        elif "грустно" in text or "печально" in text:
            meta.emotion = "sad"
            meta.reason = "грусть"

        elif "с усмешкой" in text or "иронично" in text:
            meta.emotion = "irony"
            meta.reason = "ирония"

        # ⏸ ПАУЗЫ
        if segment.original_text.endswith("..."):
            meta.pause_after_ms = 600
            meta.reason = (meta.reason or "") + " | многоточие"

        if segment.original_text.startswith("—"):
            meta.pause_before_ms = 200

        segment.tts_meta = meta



def save_to_file(filename: str, content: str, stage_name: str):
    """Сохраняет результат в файл с метаинформацией"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = Path(f"debug_output/{timestamp}_{filename}")
    filepath.parent.mkdir(exist_ok=True)

    header = f"=== {stage_name} ===\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nФайл: {filename}\n\n"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(header + content)

    print(f"💾 Сохранено: {filepath}")
    return filepath


def save_json(filename: str, data, stage_name: str):
    """Сохраняет данные в JSON файл"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = Path(f"debug_output/{timestamp}_{filename}")
    filepath.parent.mkdir(exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"💾 JSON сохранен: {filepath}")
    return filepath


def debug_run(book_path: str):
    # Создаем папку для результатов
    output_dir = Path("debug_output")
    output_dir.mkdir(exist_ok=True)

    print("=" * 80)
    print(f"📘 DEBUG PIPELINE RUN: {book_path}")
    print(f"📁 Результаты будут сохранены в: {output_dir}/")
    print("=" * 80)

    path = Path(book_path)
    book_name = path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ---------- Stage 0.1 ----------
    print("\n🟦 Stage 0.1 — FormatDetector")
    fmt = FormatDetector().detect(path)
    print(f"Формат: {fmt}")

    # Сохраняем результат Stage 0.1
    stage0_1_content = f"Формат книги: {fmt}\nПуть: {path}\nРазмер: {path.stat().st_size} bytes"
    save_to_file(f"{book_name}_stage0_1_format.txt", stage0_1_content, "Stage 0.1 - FormatDetector")

    # ---------- Stage 0.2 ----------
    print("\n🟦 Stage 0.2 — FormatParser")
    raw_text = FormatParser().parse(path, fmt)
    print(f"Raw size: {len(raw_text)} chars")

    # Сохраняем сырой текст
    save_to_file(f"{book_name}_stage0_2_raw_text.txt", raw_text, "Stage 0.2 - FormatParser")

    # ---------- Stage 0.3 ----------
    print("\n🟦 Stage 0.3 — TextExtractor")
    normalized = TextExtractor().extract(raw_text, fmt)

    # Сохраняем нормализованные строки
    lines_content = "\n".join([f"{i + 1:04d}. {line}" for i, line in enumerate(normalized.lines)])
    save_to_file(f"{book_name}_stage0_3_normalized.txt", lines_content, "Stage 0.3 - TextExtractor")

    # ---------- Stage 1.1 ----------
    print("\n🟦 Stage 1.1 — ChapterParser")
    chapters = ChapterParser().parse(normalized)

    # Сохраняем главы
    chapters_content = ""
    for chapter in chapters:
        chapters_content += f"Глава {chapter.index}: {chapter.title or 'Без названия'}\n"
        chapters_content += f"Строк: {len(chapter.lines)}\n"
        chapters_content += "Первые 3 строки:\n"
        for i, line in enumerate(chapter.lines[:3]):
            chapters_content += f"  {i + 1}. {line[:100]}...\n"
        chapters_content += "\n" + "-" * 50 + "\n"

    save_to_file(f"{book_name}_stage1_1_chapters.txt", chapters_content, "Stage 1.1 - ChapterParser")

    # ---------- Stage 1.2 ----------
    print("\n🟦 Stage 1.2 — LineTypeParser")
    lines_from_stage1_2 = LineTypeParser().parse(chapters)

    # Сохраняем линии с типами
    lines_content = ""
    for i, line in enumerate(lines_from_stage1_2):
        lines_content += f"{i + 1:04d}. [{line.type.upper():8}] {line.original}\n"

    save_to_file(f"{book_name}_stage1_2_lines.txt", lines_content, "Stage 1.2 - LineTypeParser")

    # Сохраняем статистика по типам
    type_stats = {}
    for line in lines_from_stage1_2:
        type_stats[line.type] = type_stats.get(line.type, 0) + 1

    stats_content = "Статистика типов строк:\n"
    for type_name, count in type_stats.items():
        percentage = (count / len(lines_from_stage1_2)) * 100
        stats_content += f"{type_name}: {count} строк ({percentage:.1f}%)\n"

    save_to_file(f"{book_name}_stage1_2_stats.txt", stats_content, "Stage 1.2 - Statistics")

    # 🔥 ---------- Stage 2.6 ----------
    print("\n🟦 Stage 2.6 — Character Collector (только сбор имен)")

    # 🔥 ИСПРАВЛЕНИЕ: передаем список Line напрямую, как в Stage 2.0
    character_data = run_character_collection(lines_from_stage1_2, save_debug=True)

    # Сохраняем детальный отчет по персонажам
    character_report = "ОТЧЕТ ПО ПЕРСОНАЖАМ КНИГИ\n"
    character_report += "=" * 60 + "\n\n"

    # Сортируем персонажей по количеству упоминаний
    sorted_chars = sorted(
        character_data.values(),
        key=lambda x: x.mention_count,
        reverse=True
    )

    character_report += f"Всего найдено персонажей: {len(character_data)}\n"
    character_report += f"Всего упоминаний: {sum(char.mention_count for char in character_data.values())}\n\n"

    character_report += "ТОП-20 ПЕРСОНАЖЕЙ:\n"
    character_report += "-" * 60 + "\n"

    for i, char in enumerate(sorted_chars[:20]):
        character_report += f"\n{i + 1:2d}. {char.name}\n"
        character_report += f"    Упоминаний: {char.mention_count}\n"
        character_report += f"    Первое упоминание: строка {char.first_occurrence}\n"
        character_report += f"    Последнее упоминание: строка {char.last_occurrence}\n"

        # Показываем примеры контекста
        if char.mentions:
            character_report += "    Примеры контекста:\n"
            for j, mention in enumerate(char.mentions[:2]):  # первые 2 примера
                character_report += f"      {j + 1}. Строка {mention.line_idx}: '{mention.context}'\n"

    save_to_file(f"{book_name}_stage2_6_characters.txt", character_report, "Stage 2.6 - Character Report")

    # Сохраняем JSON с детальными данными
    character_json = {
        "metadata": {
            "book_name": book_name,
            "total_characters": len(character_data),
            "total_mentions": sum(char.mention_count for char in character_data.values()),
            "timestamp": timestamp
        },
        "characters": {
            char.name: {
                "mention_count": char.mention_count,
                "first_occurrence": char.first_occurrence,
                "last_occurrence": char.last_occurrence,
                "mentions": [
                    {
                        "line_idx": mention.line_idx,
                        "context": mention.context,
                        "full_line": mention.line_text[:200]  # первые 200 символов строки
                    }
                    for mention in char.mentions
                ]
            }
            for char in sorted_chars
        }
    }

    save_json(f"{book_name}_stage2_6_characters.json", character_json, "Stage 2.6 - Character Data")

    # 🔥 ---------- Stage 2.0 ----------
    print("\n🔍 Stage 2.0 — Анализ глаголов книги")

    # Подготавливаем линии для Stage 2 (тот же самый список, CharacterCollector не изменил его)
    for i, line in enumerate(lines_from_stage1_2):
        line.idx = i
        if not hasattr(line, 'remarks') or line.remarks is None:
            line.remarks = []

    ubf = UserBookFormat(lines=lines_from_stage1_2)

    # Настраиваем резолвер с анализом глаголов
    config = SpeakerResolverConfig(
        confidence_threshold=0.3,
        use_narrator_fallback=True,
        debug_detailed=True,
        analyze_verbs=True
    )

    resolver = SpeakerResolver(config)

    # Запускаем Stage 2.0 + Stage 2.1 вместе
    print("🔍 Определение спикеров с анализом глаголов...")
    lines_with_speakers = resolver.process(ubf).lines

    # 🔥 СОХРАНЯЕМ СЛОВАРЬ ГЛАГОЛОВ Stage 2.0
    print("💾 Сохраняем словарь глаголов...")

    if hasattr(resolver, 'verb_dictionary'):
        verb_dict = resolver.verb_dictionary
        dict_content = "ДИНАМИЧЕСКИЙ СЛОВАРЬ ГЛАГОЛОВ\n"
        dict_content += "=" * 50 + "\n\n"

        dict_content += f"ГЛАГОЛЫ МУЖСКОГО РОДА ({len(verb_dict.male_verbs)}):\n"
        dict_content += ", ".join(sorted(verb_dict.male_verbs)) + "\n\n"

        dict_content += f"ГЛАГОЛЫ ЖЕНСКОГО РОДА ({len(verb_dict.female_verbs)}):\n"
        dict_content += ", ".join(sorted(verb_dict.female_verbs)) + "\n\n"

        dict_content += f"БАЗОВЫЕ ФОРМЫ ({len(verb_dict.verb_base_forms)}):\n"
        for base, gender in verb_dict.verb_base_forms.items():
            dict_content += f"  {base} → {gender}\n"

        save_to_file(f"{book_name}_stage2_0_verb_dictionary.txt", dict_content, "Stage 2.0 - Verb Dictionary")

    # 🔥 СОХРАНЯЕМ ПОЛНЫЕ РЕЗУЛЬТАТЫ Stage 2.1
    print("💾 Сохраняем результаты определения спикеров...")

    # 1. Полный текст книги со спикерами
    book_with_speakers = ""
    for i, line in enumerate(lines_with_speakers):
        if line.type == "dialogue":
            speaker_icon = "👨" if line.speaker == "male" else "👩" if line.speaker == "female" else "🗣️"
            book_with_speakers += f"{speaker_icon} {i + 1:04d}. {line.speaker.upper()}: {line.original}\n"
        else:
            book_with_speakers += f"📝 {i + 1:04d}. NARRATOR: {line.original}\n"

    save_to_file(f"{book_name}_stage2_1_full_book.txt", book_with_speakers, "Stage 2.1 - Full Book with Speakers")

    # 2. Только диалоги
    dialogue_lines = [l for l in lines_with_speakers if l.type == "dialogue"]
    dialogues_content = ""
    for i, line in enumerate(dialogue_lines):
        speaker_icon = "👨" if line.speaker == "male" else "👩"
        dialogues_content += f"{speaker_icon} {i + 1:04d}. {line.speaker.upper()}: {line.original}\n"

    save_to_file(f"{book_name}_stage2_1_dialogues_only.txt", dialogues_content, "Stage 2.1 - Dialogues Only")

    # 3. Детальная статистика
    stats_content = "ДЕТАЛЬНАЯ СТАТИСТИКА SPEAKER RESOLVER\n"
    stats_content += "=" * 50 + "\n\n"

    total_lines = len(lines_with_speakers)
    dialogue_count = len(dialogue_lines)

    stats_content += f"Всего строк: {total_lines}\n"
    stats_content += f"Диалоговых строк: {dialogue_count} ({dialogue_count / total_lines * 100:.1f}%)\n\n"

    # Распределение спикеров
    speaker_stats = {}
    for line in lines_with_speakers:
        speaker = line.speaker if line.speaker else "unknown"
        speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

    stats_content += "РАСПРЕДЕЛЕНИЕ СПИКЕРОВ:\n"
    for speaker, count in speaker_stats.items():
        percentage = (count / total_lines) * 100
        stats_content += f"  {speaker}: {count} строк ({percentage:.1f}%)\n"

    # Статистика словаря глаголов
    if hasattr(resolver, 'verb_dictionary'):
        verb_dict = resolver.verb_dictionary
        stats_content += f"\nСЛОВАРЬ ГЛАГОЛОВ:\n"
        stats_content += f"  Глаголов м.р.: {len(verb_dict.male_verbs)}\n"
        stats_content += f"  Глаголов ж.р.: {len(verb_dict.female_verbs)}\n"
        stats_content += f"  Базовых форм: {len(verb_dict.verb_base_forms)}\n"

    # Анализ качества
    male_verbs = ["спросил", "скомандовал", "выдохнул", "произнес", "ответил"]
    female_verbs = ["доложила", "сообщила", "сказала", "спросила", "ответила"]

    verified = []
    for line in dialogue_lines:
        text_lower = line.original.lower()
        expected = None
        for verb in male_verbs:
            if verb in text_lower:
                expected = "male"
                break
        for verb in female_verbs:
            if verb in text_lower:
                expected = "female"
                break

        if expected:
            verified.append((line, expected))

    if verified:
        correct = sum(1 for line, expected in verified if line.speaker == expected)
        accuracy = (correct / len(verified)) * 100
        stats_content += f"\nАНАЛИЗ КАЧЕСТВА:\n"
        stats_content += f"Проверяемых строк: {len(verified)}\n"
        stats_content += f"Правильно: {correct}\n"
        stats_content += f"Точность: {accuracy:.1f}%\n"

    save_to_file(f"{book_name}_stage2_1_statistics.txt", stats_content, "Stage 2.1 - Detailed Statistics")

    # 4. JSON со всеми данными
    book_data = {
        "metadata": {
            "book_name": book_name,
            "total_lines": total_lines,
            "dialogue_lines": dialogue_count,
            "timestamp": timestamp
        },
        "lines": [
            {
                "id": line.id,
                "index": i,
                "type": line.type,
                "speaker": line.speaker,
                "text": line.original,
                "chapter": line.chapter_id
            }
            for i, line in enumerate(lines_with_speakers)
        ],
        "statistics": speaker_stats
    }

    save_json(f"{book_name}_stage2_1_complete.json", book_data, "Stage 2.1 - Complete Data")

    # ---------- Stage 1.3-1.5 ----------
    print("\n🟦 Stage 1.3-1.5 — Сегментация и обработка для TTS")

    # Берем sample для сегментации (первые 50 строк)
    sample_lines = lines_with_speakers[:50]

    # Stage 1.3 — SegmentAnalyzer
    print("📊 SegmentAnalyzer...")
    analyzer = SegmentAnalyzer()
    all_segments = []

    for line in sample_lines:
        segs = analyzer.split(line)
        for seg in segs:
            seg.speaker = line.speaker
        all_segments.extend(segs)

    # Сохраняем сегменты
    segments_content = "СЕГМЕНТЫ (первые 50 строк)\n"
    segments_content += "=" * 50 + "\n\n"

    for seg in all_segments:
        speaker_icon = "👨" if seg.speaker == "male" else "👩" if seg.speaker == "female" else "📝"
        segments_content += f"{speaker_icon} [L{seg.line_id}:{seg.kind}] {seg.speaker}: {seg.original_text}\n"

    save_to_file(f"{book_name}_stage1_3_segments.txt", segments_content, "Stage 1.3 - Segments")

    # Stage 1.4 — SegmentTextAdapter
    print("🔧 SegmentTextAdapter...")
    adapter = SegmentTextAdapter()
    for i, seg in enumerate(all_segments):
        adapter.adapt(seg, is_last=(i == len(all_segments) - 1))

    tts_content = "TTS ТЕКСТ (первые 50 строк)\n"
    tts_content += "=" * 50 + "\n\n"

    for seg in all_segments:
        tts_content += f"[L{seg.line_id}:{seg.kind}] {seg.speaker}: {seg.tts_text}\n"

    save_to_file(f"{book_name}_stage1_4_tts.txt", tts_content, "Stage 1.4 - TTS Text")

    # Stage 1.5 — StressPlaceholder
    print("🎯 StressPlaceholder...")
    stress = StressPlaceholder()
    for seg in all_segments:
        stress.apply(seg)

    stress_content = "STRESS MAPS (первые 50 строк)\n"
    stress_content += "=" * 50 + "\n\n"

    for seg in all_segments:
        stress_content += f"[L{seg.line_id}] {seg.speaker}: {seg.stress_map}\n"

    save_to_file(f"{book_name}_stage1_5_stress.txt", stress_content, "Stage 1.5 - Stress Maps")

    # 🔥 ФИНАЛЬНЫЙ ОТЧЕТ
    print("\n" + "=" * 80)
    print("📊 ФИНАЛЬНЫЙ ОТЧЕТ")
    print("=" * 80)

    final_report = f"""
ФИНАЛЬНЫЙ ОТЧЕТ ПО ОБРАБОТКЕ КНИГИ
Книга: {book_name}
Время обработки: {timestamp}
Общее количество строк: {total_lines}

# ---------- Stage 3 ----------
print("\n🎼 Stage 3 — TTS Director")

director = TTSDirector()

for seg in all_segments:
    director.apply(seg)

director_content = "TTS META (первые 50 строк)\n"
director_content += "=" * 50 + "\n\n"

for seg in all_segments:
    director_content += (
        f"[L{seg.line_id}:{seg.kind}] {seg.speaker}\n"
        f"TEXT: {seg.original_text}\n"
        f"META: {seg.tts_meta}\n\n"
    )

save_to_file(
    f"{book_name}_stage3_tts_director.txt",
    director_content,
    "Stage 3 - TTS Director"
)

СТАТИСТИКА:
- Диалоговых строк: {dialogue_count} ({dialogue_count / total_lines * 100:.1f}%)
- Narrator строк: {total_lines - dialogue_count}
- Распределение спикеров: {speaker_stats}
- Найдено персонажей: {len(character_data)}

ФАЙЛЫ РЕЗУЛЬТАТОВ:
• {book_name}_stage0_1_format.txt - Формат книги
• {book_name}_stage0_2_raw_text.txt - Исходный текст
• {book_name}_stage0_3_normalized.txt - Нормализованные строки
• {book_name}_stage1_1_chapters.txt - Разбивка на главы
• {book_name}_stage1_2_lines.txt - Типы строк
• {book_name}_stage2_6_characters.txt - Отчет по персонажам
• {book_name}_stage2_6_characters.json - Данные по персонажам
• {book_name}_stage2_0_verb_dictionary.txt - Словарь глаголов
• {book_name}_stage2_1_full_book.txt - Полный текст со спикерами
• {book_name}_stage2_1_dialogues_only.txt - Только диалоги
• {book_name}_stage2_1_statistics.txt - Статистика
• {book_name}_stage2_1_complete.json - Полные данные JSON
• {book_name}_stage1_3_segments.txt - Сегменты
• {book_name}_stage1_4_tts.txt - TTS текст
• {book_name}_stage1_5_stress.txt - Stress maps

Обработка завершена успешно! ✅
"""

    print(final_report)
    save_to_file(f"{book_name}_FINAL_REPORT.txt", final_report, "FINAL REPORT")

    print("🎉 ВСЕ ФАЙЛЫ СОХРАНЕНЫ В ПАПКЕ debug_output/")


if __name__ == "__main__":
    debug_run("book.fb2")

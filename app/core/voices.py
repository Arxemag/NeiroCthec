"""
Реестр голосов для отдачи в API (список спикеров с ролями: диктор, мужской, женский).
Использует TTS_VOICES_ROOT и SHARED_STORAGE_ROOT, без зависимости от tts_engine_service.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

# Роли для UI: три колонки в личном кабинете
VOICE_ROLE_NARRATOR = "narrator"
VOICE_ROLE_MALE = "male"
VOICE_ROLE_FEMALE = "female"

# Маппинг id -> роль (для встроенных и типичных имён)
_ID_TO_ROLE: dict[str, str] = {
    "narrator": VOICE_ROLE_NARRATOR,
    "male": VOICE_ROLE_MALE,
    "female": VOICE_ROLE_FEMALE,
    "default": VOICE_ROLE_NARRATOR,
    "main": VOICE_ROLE_NARRATOR,
    "storyteller": VOICE_ROLE_NARRATOR,
    "woman": VOICE_ROLE_FEMALE,
    "girl": VOICE_ROLE_FEMALE,
    "man": VOICE_ROLE_MALE,
    "boy": VOICE_ROLE_MALE,
}

# Человекочитаемые названия для встроенных ролей
_ROLE_DISPLAY_NAMES: dict[str, str] = {
    VOICE_ROLE_NARRATOR: "Диктор",
    VOICE_ROLE_MALE: "Мужской голос",
    VOICE_ROLE_FEMALE: "Женский голос",
}


def _app_root() -> Path:
    """Корень приложения (папка app/), чтобы не зависеть от текущей рабочей директории."""
    return Path(__file__).resolve().parent.parent


def _voices_root() -> Path:
    raw = os.getenv("TTS_VOICES_ROOT", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else _app_root() / raw
    return _app_root() / "storage" / "voices"


def _shared_storage_root() -> Path:
    return Path(os.getenv("SHARED_STORAGE_ROOT", "/srv/storage"))


def _resolve_role(voice_id: str) -> str:
    """Определяет роль по id: narrator, male или female."""
    raw = (voice_id or "").strip().lower().replace(" ", "_")
    if raw in _ID_TO_ROLE:
        return _ID_TO_ROLE[raw]
    if raw.startswith("narrator_"):
        return VOICE_ROLE_NARRATOR
    if raw.startswith("male_"):
        return VOICE_ROLE_MALE
    if raw.startswith("female_"):
        return VOICE_ROLE_FEMALE
    return VOICE_ROLE_NARRATOR


def _display_name(voice_id: str, role: str) -> str:
    """Человекочитаемое имя для голоса."""
    if role == VOICE_ROLE_NARRATOR and voice_id == "narrator":
        return _ROLE_DISPLAY_NAMES[VOICE_ROLE_NARRATOR]
    if role == VOICE_ROLE_MALE and voice_id == "male":
        return _ROLE_DISPLAY_NAMES[VOICE_ROLE_MALE]
    if role == VOICE_ROLE_FEMALE and voice_id == "female":
        return _ROLE_DISPLAY_NAMES[VOICE_ROLE_FEMALE]
    # narrator_1 -> "Диктор 1", male_2 -> "Мужской голос 2"
    if voice_id.startswith("narrator_"):
        suffix = voice_id[len("narrator_"):].lstrip("_")
        return f"{_ROLE_DISPLAY_NAMES[VOICE_ROLE_NARRATOR]} {suffix}" if suffix else _ROLE_DISPLAY_NAMES[VOICE_ROLE_NARRATOR]
    if voice_id.startswith("male_"):
        suffix = voice_id[len("male_"):].lstrip("_")
        return f"{_ROLE_DISPLAY_NAMES[VOICE_ROLE_MALE]} {suffix}" if suffix else _ROLE_DISPLAY_NAMES[VOICE_ROLE_MALE]
    if voice_id.startswith("female_"):
        suffix = voice_id[len("female_"):].lstrip("_")
        return f"{_ROLE_DISPLAY_NAMES[VOICE_ROLE_FEMALE]} {suffix}" if suffix else _ROLE_DISPLAY_NAMES[VOICE_ROLE_FEMALE]
    return voice_id.replace("_", " ").title() or voice_id


class VoiceEntry(TypedDict):
    id: str
    path: str
    source: str
    role: str
    name: str


def get_voice_registry() -> list[VoiceEntry]:
    """
    Собирает список голосов: встроенные (narrator, male, female) + обнаруженные .wav в TTS_VOICES_ROOT.
    Каждый голос имеет id, path, source, role (narrator|male|female), name (для отображения).
    """
    result: list[VoiceEntry] = []
    seen: set[str] = set()
    root = _voices_root()
    shared_voices = _shared_storage_root() / "voices"

    # 1) Встроенные: narrator.wav, male.wav, female.wav
    for sid, fn in [("narrator", "narrator.wav"), ("male", "male.wav"), ("female", "female.wav")]:
        for base in (root, shared_voices):
            p = base / fn
            if p.exists():
                path_str = str(p.resolve())
                role = _resolve_role(sid)
                result.append(VoiceEntry(
                    id=sid,
                    path=path_str,
                    source="builtin",
                    role=role,
                    name=_display_name(sid, role),
                ))
                seen.add(sid)
                break

    # 2) Обнаруженные .wav: имя файла без расширения = id
    for base in (root, shared_voices):
        if not base.exists():
            continue
        for f in sorted(base.glob("*.wav")):
            sid = f.stem.lower()
            if not sid or sid in seen:
                continue
            seen.add(sid)
            role = _resolve_role(sid)
            result.append(VoiceEntry(
                id=sid,
                path=str(f.resolve()),
                source="discovered",
                role=role,
                name=_display_name(sid, role),
            ))

    return result


def get_voice_path(voice_id: str) -> str | None:
    """Возвращает абсолютный путь к файлу сэмпла по id или None."""
    for v in get_voice_registry():
        if v["id"] == voice_id:
            return v["path"]
    return None

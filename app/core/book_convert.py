# core/book_convert.py — извлечение текста из fb2, epub, mobi для пайплайна озвучки.
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


# Namespace для FB2
FB2_NS = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}


def _collect_text_from_element(elem: ET.Element, parts: list[str]) -> None:
    """Рекурсивно собирает текст из элемента XML (FB2)."""
    if elem.text and elem.text.strip():
        parts.append(elem.text.strip())
    for child in elem:
        _collect_text_from_element(child, parts)
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())


def extract_text_from_fb2(path: Path) -> str:
    """Извлекает текст из FB2 (FictionBook 2) — XML."""
    tree = ET.parse(path)
    root = tree.getroot()
    ns = "http://www.gribuser.ru/xml/fictionbook/2.0"
    ns_alt = "http://www.gribuser.ru/xml/fictionbook/2.0/gribuser.ru"
    parts: list[str] = []
    for body in root.iter():
        tag = body.tag
        if tag in ("body", f"{{{ns}}}body", f"{{{ns_alt}}}body"):
            _collect_text_from_element(body, parts)
    text = "\n".join(p for p in parts if p)
    return _normalize_whitespace(text)


def extract_text_from_epub(path: Path) -> str:
    """Извлекает текст из EPUB (ZIP с XHTML)."""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError as e:
        raise RuntimeError("Для поддержки EPUB установите: pip install ebooklib") from e
    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        try:
            content = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            continue
        parts.append(_html_to_text(content))
    text = "\n\n".join(p for p in parts if p.strip())
    return _normalize_whitespace(text)


def extract_text_from_mobi(path: Path) -> str:
    """Извлекает текст из MOBI (AZW). Использует пакет mobi (извлечение в HTML/EPUB)."""
    try:
        import mobi
        import shutil
    except ImportError as e:
        raise RuntimeError("Для поддержки MOBI установите: pip install mobi") from e
    try:
        temp_dir, extracted_path = mobi.extract(str(path))
    except Exception as e:
        raise RuntimeError(f"Не удалось прочитать MOBI: {e}") from e
    if not extracted_path or not Path(extracted_path).exists():
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        raise RuntimeError("MOBI: не удалось извлечь содержимое")
    p = Path(extracted_path)
    try:
        if p.suffix.lower() == ".epub":
            return extract_text_from_epub(p)
        content = p.read_text(encoding="utf-8", errors="replace")
        return _normalize_whitespace(_html_to_text(content))
    finally:
        try:
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def _html_to_text(html: str) -> str:
    """Упрощённое извлечение текста из HTML/XHTML."""
    # Убираем теги script/style
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    # Заменяем блочные теги на переносы
    html = re.sub(r"</(p|div|br|tr|h[1-6]|li)[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Убираем все теги
    text = re.sub(r"<[^>]+>", "", html)
    # Декодируем сущности
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    return _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    """Схлопывает множественные пробелы и пустые строки."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def book_to_text(path: Path) -> str:
    """По расширению файла извлекает текст. Возвращает чистый текст для парсера."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".fb2":
        return extract_text_from_fb2(path)
    if suffix == ".epub":
        return extract_text_from_epub(path)
    if suffix == ".mobi":
        return extract_text_from_mobi(path)
    raise ValueError(f"Неизвестный формат книги: {suffix}")

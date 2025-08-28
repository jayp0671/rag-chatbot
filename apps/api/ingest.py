from __future__ import annotations
import re
from typing import List
from PyPDF2 import PdfReader  # PyPDF2 is installed as pypdf2

def extract_text_from_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
    except Exception:
        return ""
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)

_whitespace_re = re.compile(r"[ \t]+")
_newlines_re = re.compile(r"\n{3,}")
_ctrl_re = re.compile(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F]")

def clean_text(text: str) -> str:
    text = _ctrl_re.sub("", text)
    text = text.replace("\r", "\n")
    text = _whitespace_re.sub(" ", text)
    text = _newlines_re.sub("\n\n", text)
    text = text.strip()
    return text

def chunk_text(text: str, target_tokens: int = 900, overlap_tokens: int = 120) -> List[str]:
    if not text:
        return []
    target_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + target_chars)
        cut = text[i:j]
        k = cut.rfind(". ")
        if k != -1 and k > int(len(cut) * 0.6):
            j = i + k + 1
            cut = text[i:j]
        cut = cut.strip()
        if len(cut) >= 200:
            chunks.append(cut)
        i = j - overlap_chars
        if i <= 0:
            i = j
    return chunks

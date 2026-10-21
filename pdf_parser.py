"""PDF / görüntüden metin okuma + belge adı ve tarih çıkarma (ücretsiz: PyMuPDF + Tesseract)."""
import io
import re
from datetime import date

_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")


def norm(s: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirip küçültür (uzunluk korunur)."""
    return s.translate(_TR).lower()


MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

NUM_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})(?!\d)")
ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
TXT_RE = re.compile(r"(?<!\d)(\d{1,2})\s+([a-z]{3,9})\.?\s+(\d{4})(?!\d)")

START_KW = ["baslangic", "duzenle", "verilis", "verildi", "verilme", "issue",
            "date of issue", "valid from", "from"]
END_KW = ["bitis", "son gecerlilik", "gecerlilik", "gecerli", "expiry", "expire",
          "valid until", "valid to", "until", "kadar", "sona er"]
SKIP_KW = ["dogum", "birth"]

# (aranacak kelime, belge adı) — kendi belge türlerini buraya ekle
DOC_HINTS = [
    ("stcw", "STCW Sertifikası"),
    ("saglik", "Sağlık Raporu"),
    ("gemiadami cuzdan", "Gemiadamı Cüzdanı"),
    ("gemi adami cuzdan", "Gemiadamı Cüzdanı"),
    ("yangin", "Yangınla Mücadele Sertifikası"),
    ("ilk yardim", "İlk Yardım Sertifikası"),
    ("psikoteknik", "Psikoteknik Belgesi"),
    ("src", "SRC Belgesi"),
    ("ehliyet", "Ehliyet"),
    ("pasaport", "Pasaport"),
    ("kimlik", "Kimlik"),
    ("sertifika", "Sertifika"),
    ("belge", "Belge"),
]


def extract_text(data: bytes, is_pdf: bool = True):
    """(metin, yöntem, tanı_bilgisi) döner. Metin katmanı yoksa OCR'a düşer."""
    from PIL import Image, ImageOps
    import pytesseract

    info = []

    def ocr(img):
        img = ImageOps.autocontrast(ImageOps.grayscale(img))
        best = ""
        for psm in (3, 6):
            cfg = f"--oem 1 --psm {psm}"
            try:
                t = pytesseract.image_to_string(img, lang="tur+eng", config=cfg)
            except pytesseract.TesseractNotFoundError:
                info.append("Tesseract kurulu değil (packages.txt repo KÖKÜNDE olmalı).")
                return ""
            except pytesseract.TesseractError as e:
                info.append(f"tur dil paketi sorunu, eng'e düşüldü: {str(e)[:120]}")
                try:
                    t = pytesseract.image_to_string(img, lang="eng", config=cfg)
                except Exception as e2:
                    info.append(f"OCR hatası: {str(e2)[:120]}")
                    return ""
            if len(t.strip()) > len(best.strip()):
                best = t
        return best

    if not is_pdf:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return ocr(img), "ocr", info

    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    pages = list(doc)[:5]
    text = "\n".join(p.get_text() for p in pages)
    info.append(f"Sayfa: {len(doc)}, metin katmanı: {len(text.strip())} karakter")
    if len(text.strip()) >= 40:
        return text, "metin", info
    out = []
    for p in pages:
        pix = p.get_pixmap(dpi=300)
        out.append(ocr(Image.open(io.BytesIO(pix.tobytes("png")))))
    text = "\n".join(out)
    info.append(f"OCR sonucu: {len(text.strip())} karakter")
    return text, "ocr", info


def find_dates(s: str):
    s = norm(s)
    found = []
    for rx, kind in ((NUM_RE, "dmy"), (ISO_RE, "ymd"), (TXT_RE, "txt")):
        for m in rx.finditer(s):
            try:
                if kind == "dmy":
                    d = date(int(m[3]), int(m[2]), int(m[1]))
                elif kind == "ymd":
                    d = date(int(m[1]), int(m[2]), int(m[3]))
                else:
                    mo = MONTHS.get(m[2]) or MONTHS.get(m[2][:3])
                    if not mo:
                        continue
                    d = date(int(m[3]), mo, int(m[1]))
            except ValueError:
                continue
            if 1990 <= d.year <= 2100:
                found.append((m.start(), d))
    return [d for _, d in sorted(found)]


def parse_dates(text: str):
    lines = [l for l in text.splitlines() if l.strip()]
    start = end = None
    all_dates = []
    for i, line in enumerate(lines):
        n = norm(line)
        if any(k in n for k in SKIP_KW):
            continue
        ds = find_dates(line)
        has_start = any(k in n for k in START_KW)
        has_end = any(k in n for k in END_KW)
        if not ds and (has_start or has_end) and i + 1 < len(lines):
            nxt = norm(lines[i + 1])
            if not any(k in nxt for k in SKIP_KW):
                ds = find_dates(lines[i + 1])
        all_dates += ds
        if not ds:
            continue
        if has_start and not (has_end and len(ds) >= 2):
            start = start or ds[0]
        elif has_end:
            if len(ds) >= 2 and start is None:
                start = ds[0]
            end = ds[-1] if end is None else max(end, ds[-1])

    if start is None and end is None:
        if len(all_dates) >= 2:
            start, end = min(all_dates), max(all_dates)
        elif len(all_dates) == 1:
            end = all_dates[0]
    elif end is None:
        cand = [d for d in all_dates if start and d > start]
        end = max(cand) if cand else None
    elif start is None:
        cand = [d for d in all_dates if d < end]
        start = min(cand) if cand else None

    if start and end and start > end:
        start, end = end, start
    return start, end


def guess_doc_name(text: str) -> str:
    n = norm(text)
    for key, name in DOC_HINTS:
        if key in n:
            return name
    for line in text.splitlines():
        line = line.strip()
        if sum(c.isalpha() for c in line) >= 4:
            return line[:80]
    return ""


def match_person(text: str, people):
    n = norm(text)
    for p in people:
        if norm(p["ad"]).strip() in n and norm(p["soyad"]).strip() in n:
            return p["id"]
    return None


def parse_document(text: str, people):
    start, end = parse_dates(text)
    return {
        "doc_name": guess_doc_name(text),
        "start": start,
        "end": end,
        "person_id": match_person(text, people),
    }

"""Fonts for caption scripts the bundled Latin/Cyrillic/Devanagari fonts cannot draw: Chinese, Japanese, Korean, Arabic.

* Arabic: a small bold Noto Sans Arabic is bundled (remotion-video/public/fonts/NotoSansArabic.ttf).
* CJK: the full Noto Sans SC/JP/KR files are 10-18 MB each, so nothing is bundled. The variable font is downloaded once into
  ~/.cache/shortsflow/fonts and, for every render, cut down (fontTools) to bold weight and just the characters of that
  transcript (plus ASCII and CJK punctuation). The result is a 20-150 KB TTF, written under a name that depends on its
  content, so the ASS reel path (libass, `\\fn<family>`) and the Remotion path (FontFace) can both use it.

Everything here degrades to "no font" (None) when offline or when fontTools is missing; callers then keep the old
behaviour (empty boxes for CJK), they never fail a render.
"""
import hashlib
import os
import re
import shutil

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "shortsflow", "fonts")
SUBSET_DIR = os.path.join(CACHE_DIR, "subsets")
_RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
CJK_SOURCES = {
    "zh": ("NotoSansSC.ttf", _RAW + "notosanssc/NotoSansSC%5Bwght%5D.ttf"),
    "ja": ("NotoSansJP.ttf", _RAW + "notosansjp/NotoSansJP%5Bwght%5D.ttf"),
    "ko": ("NotoSansKR.ttf", _RAW + "notosanskr/NotoSansKR%5Bwght%5D.ttf"),
}
SUBSET_PREFIX = "SFCJK"
SUBSET_NAME_RE = re.compile(SUBSET_PREFIX + r"-(?:zh|ja|ko)-[0-9a-f]{8}")
ARABIC_FONT = "Noto Sans Arabic"

def _cls(*ranges):
    return re.compile("[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in ranges) + "]")


_HAN = _cls((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))
_KANA = _cls((0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F))
_HANGUL = _cls((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
# Hebrew .. Arabic Extended-A, plus presentation forms A and B
_RTL = _cls((0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFF))
_ARABIC = _cls((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
# always kept in a CJK subset: ASCII, general/CJK punctuation, full-width forms
_KEEP_RANGES = [(0x20, 0x7E), (0x2000, 0x206F), (0x3000, 0x303F), (0xFF00, 0xFFEF)]


def has_rtl(text):
    return bool(_RTL.search(text or ""))


def has_arabic(text):
    return bool(_ARABIC.search(text or ""))


def cjk_language(text, hint=None):
    """'ja' | 'ko' | 'zh' for text that contains CJK characters, else None.
    Kana means Japanese and Hangul means Korean; Han characters alone are Chinese unless `hint` says ja/ko/zh."""
    text = text or ""
    if _KANA.search(text):
        return "ja"
    if _HANGUL.search(text):
        return "ko"
    if _HAN.search(text):
        h = (hint or "").lower()[:2]
        return h if h in CJK_SOURCES else "zh"
    return None


def _download(url, dest):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "shortsflow-font-fetch"})
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, dest)


def ensure_base_font(lang, download=_download, cache_dir=None):
    """Path of the full Noto Sans CJK font for `lang`, downloading it on first use. None when it cannot be had."""
    if lang not in CJK_SOURCES:
        return None
    name, url = CJK_SOURCES[lang]
    folder = cache_dir or CACHE_DIR
    path = os.path.join(folder, name)
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        return path
    try:
        os.makedirs(folder, exist_ok=True)
        print(f"[Log] Downloading the {lang} caption font (first time only, ~10-18 MB)...")
        download(url, path)
        if os.path.getsize(path) < 1_000_000:
            raise OSError("downloaded file is too small")
        return path
    except Exception as e:
        print(f"[Warning] Could not get the {lang} caption font ({e}); those captions may show empty boxes.")
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def _wanted_codepoints(text):
    chars = {ord(c) for c in text or "" if not c.isspace() or c == " "}
    for lo, hi in _KEEP_RANGES:
        chars.update(range(lo, hi + 1))
    return chars


def subset_font(src, dest, codepoints, family, weight=700):
    """Write `dest`: `src` (variable fonts pinned to `weight`) reduced to `codepoints`, named `family` (Bold style)."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    font = TTFont(src)
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.notdef_outline = True
    opts.hinting = False
    opts.name_IDs = ["*"]
    opts.glyph_names = False
    opts.drop_tables += ["DSIG"]
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=sorted(codepoints))
    sub.subset(font)
    if "fvar" in font:
        from fontTools.varLib import instancer
        limits = {}
        for axis in font["fvar"].axes:
            if axis.axisTag == "wght":
                limits["wght"] = max(axis.minValue, min(axis.maxValue, weight))
            elif axis.axisTag == "wdth":
                limits["wdth"] = 100
            else:
                limits[axis.axisTag] = axis.defaultValue
        font = instancer.instantiateVariableFont(font, limits, inplace=False)
    if family:
        names = font["name"]
        names.names = [n for n in names.names if n.nameID not in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25)]
        for nid, value in ((1, family), (2, "Bold"), (3, family + "-Bold"), (4, family + " Bold"), (6, family.replace(" ", "") + "-Bold")):
            names.setName(value, nid, 3, 1, 0x409)
    if "OS/2" in font:
        font["OS/2"].usWeightClass = 700
        font["OS/2"].fsSelection = (font["OS/2"].fsSelection | 0x20) & ~0x41
    font["head"].macStyle |= 1
    font.save(dest)
    return dest


def cjk_subset(text, hint=None, out_dir=None, download=_download, cache_dir=None):
    """(family, path) of a bold CJK font containing every character of `text`, or None if the text has no CJK or the font
    is unavailable. The family name changes with the character set, so different subsets never clash in a font cache."""
    lang = cjk_language(text, hint)
    if not lang:
        return None
    cps = _wanted_codepoints(text)
    digest = hashlib.sha1(",".join(map(str, sorted(cps))).encode()).hexdigest()[:8]
    family = f"{SUBSET_PREFIX}-{lang}-{digest}"
    folder = os.path.join(cache_dir, "subsets") if cache_dir else SUBSET_DIR
    path = os.path.join(folder, family + ".ttf")
    if not os.path.exists(path):
        base = ensure_base_font(lang, download=download, cache_dir=cache_dir)
        if not base:
            return None
        try:
            os.makedirs(folder, exist_ok=True)
            subset_font(base, path, cps, family)
        except Exception as e:
            print(f"[Warning] Could not build the {lang} caption font ({e}); those captions may show empty boxes.")
            return None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, family + ".ttf")
        if not os.path.exists(dest):
            shutil.copyfile(path, dest)
        path = dest
    return family, path


def subset_files_for(ass_text, folder):
    """Subset font files named in an ASS document (`\\fnSFCJK-ja-1234abcd`) that exist in the cache."""
    out = []
    for name in sorted(set(SUBSET_NAME_RE.findall(ass_text or ""))):
        path = os.path.join(folder, name + ".ttf")
        if os.path.exists(path):
            out.append(path)
    return out

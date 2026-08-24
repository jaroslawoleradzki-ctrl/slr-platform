"""Central language canonicalization for the SLR platform.

Provides deterministic, idempotent normalization of language values to
ISO 639-1 two-letter lowercase codes.
"""

from __future__ import annotations

# Canonical ISO 639-1 two-letter codes (explicit set of valid outputs)
_CANONICAL_ISO_639_1: set[str] = {
    "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av",
    "ay", "az", "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo",
    "br", "bs", "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv",
    "cy", "da", "de", "dv", "dz", "ee", "el", "en", "eo", "es",
    "et", "eu", "fa", "ff", "fi", "fj", "fo", "fr", "fy", "ga",
    "gd", "gl", "gn", "gu", "gv", "ha", "he", "hi", "ho", "hr",
    "ht", "hu", "hy", "hz", "ia", "id", "ie", "ig", "ii", "ik",
    "io", "is", "it", "iu", "ja", "jv", "ka", "kg", "ki", "kj",
    "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw",
    "ky", "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv",
    "ny", "oc", "oj", "om", "or", "os", "pa", "pi", "pl", "ps",
    "pt", "qu", "rm", "rn", "ro", "ru", "rw", "sa", "sc", "sd",
    "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr",
    "ss", "st", "su", "sv", "sw", "ta", "te", "tg", "th", "ti",
    "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty", "ug",
    "uk", "ur", "uz", "ve", "vi", "vo", "wa", "wo", "xh", "yi",
    "yo", "za", "zh", "zu",
}

# Mapping from various language codes/names to canonical ISO 639-1
# Includes ISO 639-2/T (terminology), ISO 639-2/B (bibliographic), and common aliases
_LANGUAGE_MAP: dict[str, str] = {
    # ISO 639-1 identity mappings
    **{code: code for code in _CANONICAL_ISO_639_1},

    # ISO 639-2/T (terminology) three-letter codes
    "aar": "aa", "abk": "ab", "ave": "ae", "afr": "af", "aka": "ak",
    "amh": "am", "arg": "an", "ara": "ar", "asm": "as", "ava": "av",
    "aym": "ay", "aze": "az", "bak": "ba", "bel": "be", "bul": "bg",
    "bih": "bh", "bis": "bi", "bam": "bm", "ben": "bn", "bod": "bo",
    "bre": "br", "bos": "bs", "cat": "ca", "che": "ce", "cha": "ch",
    "cos": "co", "cre": "cr", "ces": "cs", "chu": "cu", "chv": "cv",
    "cym": "cy", "dan": "da", "deu": "de", "div": "dv", "dzo": "dz",
    "ewe": "ee", "ell": "el", "eng": "en", "epo": "eo", "spa": "es",
    "est": "et", "eus": "eu", "fas": "fa", "ful": "ff", "fin": "fi",
    "fij": "fj", "fao": "fo", "fra": "fr", "fry": "fy", "gle": "ga",
    "gla": "gd", "glg": "gl", "grn": "gn", "guj": "gu", "glv": "gv",
    "hau": "ha", "heb": "he", "hin": "hi", "hmo": "ho", "hrv": "hr",
    "hat": "ht", "hun": "hu", "hye": "hy", "her": "hz", "ina": "ia",
    "ind": "id", "ile": "ie", "ibo": "ig", "iii": "ii", "iku": "iu",
    "ipk": "ik", "ido": "io", "isl": "is", "ita": "it", "jpn": "ja", "jav": "jv",
    "kat": "ka", "kik": "ki", "kua": "kj", "kan": "kn", "kas": "ks", "kal": "kl",
    "kau": "kr", "kur": "ku", "kom": "kv", "kon": "kg", "cor": "kw", "kir": "ky",
    "lat": "la", "ltz": "lb", "lug": "lg", "lim": "li", "lin": "ln",
    "lao": "lo", "lit": "lt", "lub": "lu", "lav": "lv", "mlg": "mg",
    "mah": "mh", "mri": "mi", "mkd": "mk", "mal": "ml", "mon": "mn",
    "mar": "mr", "msa": "ms", "mlt": "mt", "mya": "my", "nau": "na",
    "nob": "nb", "nde": "nd", "nep": "ne", "ndo": "ng", "nld": "nl",
    "nno": "nn", "nor": "no", "nbl": "nr", "nav": "nv", "nya": "ny",
    "oci": "oc", "oji": "oj", "orm": "om", "ori": "or", "oss": "os",
    "pan": "pa", "pli": "pi", "pol": "pl", "pus": "ps", "por": "pt",
    "que": "qu", "roh": "rm", "run": "rn", "ron": "ro", "rus": "ru",
    "kin": "rw", "san": "sa", "srd": "sc", "snd": "sd", "sme": "se",
    "sag": "sg", "sin": "si", "slk": "sk", "slv": "sl", "smo": "sm",
    "sna": "sn", "som": "so", "sqi": "sq", "srp": "sr", "ssw": "ss",
    "sot": "st", "sun": "su", "swe": "sv", "swa": "sw", "tam": "ta",
    "tel": "te", "tgk": "tg", "tha": "th", "tir": "ti", "tuk": "tk",
    "tgl": "tl", "tsn": "tn", "ton": "to", "tur": "tr", "tso": "ts",
    "tat": "tt", "twi": "tw", "tah": "ty", "uig": "ug", "ukr": "uk",
    "urd": "ur", "uzb": "uz", "ven": "ve", "vie": "vi", "vol": "vo",
    "wln": "wa", "wol": "wo", "xho": "xh", "yid": "yi", "yor": "yo",
    "zha": "za", "zho": "zh", "zul": "zu", "kor": "ko", "kaz": "kk",
    "khm": "km",

    # ISO 639-2/B (bibliographic) three-letter codes where different from 639-2/T
    "ger": "de",  # deu (T) / ger (B)
    "fre": "fr",  # fra (T) / fre (B)
    "cze": "cs",  # ces (T) / cze (B)
    "gre": "el",  # ell (T) / gre (B)
    "dut": "nl",  # nld (T) / dut (B)
    "chi": "zh",  # zho (T) / chi (B)
    "baq": "eu",  # eus (T) / baq (B)
    "wel": "cy",  # cym (T) / wel (B)
    "arm": "hy",  # hye (T) / arm (B)
    "geo": "ka",  # kat (T) / geo (B)
    "per": "fa",  # fas (T) / per (B)
    "mac": "mk",  # mkd (T) / mac (B)
    "rum": "ro",  # ron (T) / rum (B)
    "slo": "sk",  # slk (T) / slo (B)
    "alb": "sq",  # sqi (T) / alb (B)
    "bur": "my",  # mya (T) / bur (B)
    "ice": "is",  # isl (T) / ice (B)
    "tib": "bo",  # bod (T) / tib (B)
    "mao": "mi",  # mri (T) / mao (B)
    "may": "ms",  # msa (T) / may (B)

    # Common natural-language name aliases (casefolded)
    "english": "en",
    "polish": "pl",
    "german": "de",
    "deutsch": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "russian": "ru",
    "arabic": "ar",
    "hindi": "hi",
    "bengali": "bn",
    "turkish": "tr",
    "vietnamese": "vi",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
    "greek": "el",
    "czech": "cs",
    "hungarian": "hu",
    "hebrew": "he",
    "thai": "th",
    "indonesian": "id",
    "malay": "ms",
    "tagalog": "tl",
    "ukrainian": "uk",
    "romanian": "ro",
    "bulgarian": "bg",
    "croatian": "hr",
    "serbian": "sr",
    "slovak": "sk",
    "slovenian": "sl",
    "estonian": "et",
    "latvian": "lv",
    "lithuanian": "lt",
    "esperanto": "eo",
    "latin": "la",
    "irish": "ga",
    "welsh": "cy",
    "basque": "eu",
    "catalan": "ca",
    "galician": "gl",
    "maltese": "mt",
    "icelandic": "is",
    "macedonian": "mk",
    "albanian": "sq",
    "georgian": "ka",
    "armenian": "hy",
    "azerbaijani": "az",
    "belarusian": "be",
    "bosnian": "bs",
    "persian": "fa",
    "urdu": "ur",
    "pashto": "ps",
    "kurdish": "ku",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "marathi": "mr",
    "gujarati": "gu",
    "punjabi": "pa",
    "oriya": "or",
    "assamese": "as",
    "nepali": "ne",
    "sinhala": "si",
    "burmese": "my",
    "khmer": "km",
    "mongolian": "mn",
    "tibetan": "bo",
    "uyghur": "ug",
    "uzbek": "uz",
    "kazakh": "kk",
    "kyrgyz": "ky",
    "tajik": "tg",
    "turkmen": "tk",
    "amharic": "am",
    "oromo": "om",
    "somali": "so",
    "swahili": "sw",
    "zulu": "zu",
    "xhosa": "xh",
    "afrikans": "af",
    "shona": "sn",
    "yoruba": "yo",
    "igbo": "ig",
    "hausa": "ha",
    "fulani": "ff",
    "wolof": "wo",
    "tswana": "tn",
    "sotho": "st",
    "tsonga": "ts",
    "venda": "ve",
    "kirundi": "rn",
    "rwanda": "rw",
    "lingala": "ln",
    "kikuyu": "ki",
    "luganda": "lg",
    "swati": "ss",
    "tshivenda": "ve",
    "ndebele": "nr",
    "chichewa": "ny",
    "setswana": "tn",
    "sesotho": "st",
    "xitsonga": "ts",
    "isindebele": "nr",
}


class LanguageNormalizer:
    """Normalize language values to canonical ISO 639-1 two-letter lowercase codes."""

    def normalize(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None

        stripped = value.strip()
        if not stripped:
            return None

        key = stripped.casefold()

        # Check standards-based mapping (ISO 639-1, 639-2/T, 639-2/B)
        if key in _LANGUAGE_MAP:
            return _LANGUAGE_MAP[key]

        # Check natural-language aliases
        if key in _LANGUAGE_MAP:
            return _LANGUAGE_MAP[key]

        return None


language_normalizer = LanguageNormalizer()


def normalize_language(value: object) -> str | None:
    """Module-level convenience function for language normalization."""
    return language_normalizer.normalize(value)

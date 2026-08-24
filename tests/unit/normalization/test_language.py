"""Tests for the language normalization module."""

import pytest

from app.normalization.language import LanguageNormalizer, normalize_language


class TestLanguageNormalizer:
    """Tests for LanguageNormalizer class and normalize_language function."""

    def test_iso_639_1_identity(self) -> None:
        """ISO 639-1 codes normalize to themselves (lowercase)."""
        for code in ["en", "pl", "de", "fr", "es", "sw", "af", "ca", "zh", "ja", "ko", "ru", "ar"]:
            assert normalize_language(code) == code
            assert normalize_language(code.upper()) == code

    def test_case_and_whitespace_insensitive(self) -> None:
        """Normalization is case and whitespace insensitive."""
        assert normalize_language("EN") == "en"
        assert normalize_language(" En  ") == "en"
        assert normalize_language("PL") == "pl"
        assert normalize_language("  pl ") == "pl"
        assert normalize_language("\ten\n") == "en"

    def test_iso_639_2t_terminology_codes(self) -> None:
        """ISO 639-2/T three-letter terminology codes map to ISO 639-1."""
        assert normalize_language("eng") == "en"
        assert normalize_language("pol") == "pl"
        assert normalize_language("deu") == "de"
        assert normalize_language("fra") == "fr"
        assert normalize_language("ces") == "cs"
        assert normalize_language("ell") == "el"
        assert normalize_language("nld") == "nl"
        assert normalize_language("zho") == "zh"
        assert normalize_language("jpn") == "ja"
        assert normalize_language("kor") == "ko"
        assert normalize_language("rus") == "ru"
        assert normalize_language("ara") == "ar"
        assert normalize_language("spa") == "es"
        assert normalize_language("ita") == "it"
        assert normalize_language("por") == "pt"
        assert normalize_language("swe") == "sv"
        assert normalize_language("nor") == "no"
        assert normalize_language("dan") == "da"
        assert normalize_language("fin") == "fi"
        assert normalize_language("hun") == "hu"
        assert normalize_language("heb") == "he"
        assert normalize_language("tha") == "th"
        assert normalize_language("ind") == "id"
        assert normalize_language("msa") == "ms"
        assert normalize_language("tgl") == "tl"
        assert normalize_language("ukr") == "uk"
        assert normalize_language("ron") == "ro"
        assert normalize_language("bul") == "bg"
        assert normalize_language("hrv") == "hr"
        assert normalize_language("srp") == "sr"
        assert normalize_language("slk") == "sk"
        assert normalize_language("slv") == "sl"
        assert normalize_language("est") == "et"
        assert normalize_language("lav") == "lv"
        assert normalize_language("lit") == "lt"
        assert normalize_language("epo") == "eo"
        assert normalize_language("lat") == "la"
        assert normalize_language("gle") == "ga"
        assert normalize_language("cym") == "cy"
        assert normalize_language("eus") == "eu"
        assert normalize_language("cat") == "ca"
        assert normalize_language("glg") == "gl"
        assert normalize_language("mlt") == "mt"
        assert normalize_language("isl") == "is"
        assert normalize_language("mkd") == "mk"
        assert normalize_language("sqi") == "sq"
        assert normalize_language("kat") == "ka"
        assert normalize_language("hye") == "hy"
        assert normalize_language("aze") == "az"
        assert normalize_language("bel") == "be"
        assert normalize_language("bos") == "bs"
        assert normalize_language("fas") == "fa"
        assert normalize_language("urd") == "ur"
        assert normalize_language("pus") == "ps"
        assert normalize_language("kur") == "ku"
        assert normalize_language("tam") == "ta"
        assert normalize_language("tel") == "te"
        assert normalize_language("kan") == "kn"
        assert normalize_language("mal") == "ml"
        assert normalize_language("mar") == "mr"
        assert normalize_language("guj") == "gu"
        assert normalize_language("pan") == "pa"
        assert normalize_language("ori") == "or"
        assert normalize_language("asm") == "as"
        assert normalize_language("nep") == "ne"
        assert normalize_language("sin") == "si"
        assert normalize_language("mya") == "my"
        assert normalize_language("khm") == "km"
        assert normalize_language("lao") == "lo"
        assert normalize_language("mon") == "mn"
        assert normalize_language("bod") == "bo"
        assert normalize_language("uig") == "ug"
        assert normalize_language("uzb") == "uz"
        assert normalize_language("kaz") == "kk"
        assert normalize_language("kir") == "ky"
        assert normalize_language("tgk") == "tg"
        assert normalize_language("tuk") == "tk"
        assert normalize_language("amh") == "am"
        assert normalize_language("orm") == "om"
        assert normalize_language("som") == "so"
        assert normalize_language("swa") == "sw"
        assert normalize_language("zul") == "zu"
        assert normalize_language("xho") == "xh"
        assert normalize_language("afr") == "af"
        assert normalize_language("sna") == "sn"
        assert normalize_language("yor") == "yo"
        assert normalize_language("ibo") == "ig"
        assert normalize_language("hau") == "ha"
        assert normalize_language("ful") == "ff"
        assert normalize_language("wol") == "wo"
        assert normalize_language("tsn") == "tn"
        assert normalize_language("sot") == "st"
        assert normalize_language("tso") == "ts"
        assert normalize_language("ven") == "ve"
        assert normalize_language("run") == "rn"
        assert normalize_language("kin") == "rw"
        assert normalize_language("lin") == "ln"
        assert normalize_language("kik") == "ki"
        assert normalize_language("lug") == "lg"
        assert normalize_language("ssw") == "ss"
        assert normalize_language("nya") == "ny"

    def test_iso_639_2b_bibliographic_codes(self) -> None:
        """ISO 639-2/B bibliographic codes (where different from 2/T) map to ISO 639-1."""
        assert normalize_language("ger") == "de"
        assert normalize_language("fre") == "fr"
        assert normalize_language("cze") == "cs"
        assert normalize_language("gre") == "el"
        assert normalize_language("dut") == "nl"
        assert normalize_language("chi") == "zh"
        assert normalize_language("baq") == "eu"
        assert normalize_language("wel") == "cy"
        assert normalize_language("arm") == "hy"
        assert normalize_language("geo") == "ka"
        assert normalize_language("per") == "fa"
        assert normalize_language("mac") == "mk"
        assert normalize_language("rum") == "ro"
        assert normalize_language("slo") == "sk"
        assert normalize_language("alb") == "sq"
        assert normalize_language("bur") == "my"
        assert normalize_language("ice") == "is"
        assert normalize_language("tib") == "bo"
        assert normalize_language("mao") == "mi"
        assert normalize_language("may") == "ms"

    def test_natural_language_aliases(self) -> None:
        """Common natural-language names map to ISO 639-1."""
        assert normalize_language("English") == "en"
        assert normalize_language("english") == "en"
        assert normalize_language("Polish") == "pl"
        assert normalize_language("polish") == "pl"
        assert normalize_language("German") == "de"
        assert normalize_language("german") == "de"
        assert normalize_language("Deutsch") == "de"
        assert normalize_language("deutsch") == "de"
        assert normalize_language("French") == "fr"
        assert normalize_language("french") == "fr"
        assert normalize_language("Spanish") == "es"
        assert normalize_language("spanish") == "es"
        assert normalize_language("Italian") == "it"
        assert normalize_language("italian") == "it"
        assert normalize_language("Portuguese") == "pt"
        assert normalize_language("portuguese") == "pt"
        assert normalize_language("Dutch") == "nl"
        assert normalize_language("dutch") == "nl"
        assert normalize_language("Chinese") == "zh"
        assert normalize_language("chinese") == "zh"
        assert normalize_language("Japanese") == "ja"
        assert normalize_language("japanese") == "ja"
        assert normalize_language("Korean") == "ko"
        assert normalize_language("korean") == "ko"
        assert normalize_language("Russian") == "ru"
        assert normalize_language("russian") == "ru"
        assert normalize_language("Arabic") == "ar"
        assert normalize_language("arabic") == "ar"
        assert normalize_language("Tagalog") == "tl"

    def test_empty_and_invalid_inputs(self) -> None:
        """Empty, None, and invalid inputs return None."""
        assert normalize_language(None) is None
        assert normalize_language("") is None
        assert normalize_language("  ") is None
        assert normalize_language("\t\n") is None
        assert normalize_language("xxx") is None
        assert normalize_language("zz") is None
        assert normalize_language("English/French") is None
        assert normalize_language("en-US") is None
        assert normalize_language("en,fr") is None
        assert normalize_language("unknown") is None
        assert normalize_language("Filipino") is None
        assert normalize_language(42) is None
        assert normalize_language({}) is None
        assert normalize_language([]) is None

    def test_idempotency(self) -> None:
        """Normalization is idempotent."""
        assert normalize_language(normalize_language("eng")) == "en"
        assert normalize_language(normalize_language("en")) == "en"
        assert normalize_language(normalize_language("EN")) == "en"
        assert normalize_language(normalize_language("English")) == "en"
        assert normalize_language(normalize_language("deu")) == "de"
        assert normalize_language(normalize_language("de")) == "de"

    def test_class_and_function_equivalence(self) -> None:
        """LanguageNormalizer class and module function behave identically."""
        normalizer = LanguageNormalizer()
        test_values = ["en", "ENG", "eng", "English", "deu", "ger", "German", "xxx", None, "", 42]
        for value in test_values:
            assert normalizer.normalize(value) == normalize_language(value)

    @pytest.mark.parametrize("code", [
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
    ])
    def test_all_canonical_iso_639_1_codes_normalize_to_themselves(self, code: str) -> None:
        """Every supported canonical ISO 639-1 code normalizes to itself."""
        result = normalize_language(code)
        assert result == code
        assert result.islower()
        assert len(result) == 2
        assert result in normalize_language.__globals__["_CANONICAL_ISO_639_1"]


class TestLanguageNormalizerRepresentativeAliases:
    """Test representative 639-2/B and 639-2/T aliases for coverage."""

    @pytest.mark.parametrize(("alias", "expected"), [
        # 639-2/T
        ("eng", "en"), ("fra", "fr"), ("spa", "es"), ("deu", "de"),
        ("ita", "it"), ("por", "pt"), ("nld", "nl"), ("zho", "zh"),
        ("jpn", "ja"), ("kor", "ko"), ("rus", "ru"), ("ara", "ar"),
        # 639-2/B (where different)
        ("ger", "de"), ("fre", "fr"), ("cze", "cs"), ("gre", "el"),
        ("dut", "nl"), ("chi", "zh"), ("baq", "eu"), ("wel", "cy"),
        ("arm", "hy"), ("geo", "ka"), ("per", "fa"), ("mac", "mk"),
        ("rum", "ro"), ("slo", "sk"), ("alb", "sq"), ("bur", "my"),
        ("ice", "is"), ("tib", "bo"),
        ("iku", "iu"), ("ipk", "ik"), ("kal", "kl"), ("kon", "kg"),
        ("mao", "mi"), ("may", "ms"),
    ])
    def test_alias_maps_to_canonical(self, alias: str, expected: str) -> None:
        assert normalize_language(alias) == expected
        assert normalize_language(alias.upper()) == expected

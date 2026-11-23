import re
import unicodedata


_UNIT_FACTORS = {
    "mm": 0.1,
    "millimeter": 0.1,
    "millimeters": 0.1,
    "millimetre": 0.1,
    "millimetres": 0.1,
    "মিলিমিটার": 0.1,
    "মিমি": 0.1,
    "मिलीमीटर": 0.1,
    "मिमी": 0.1,
    "milimetro": 0.1,
    "milimetros": 0.1,
    "milímetro": 0.1,
    "milímetros": 0.1,
    "millimètre": 0.1,
    "millimètres": 0.1,
    "ملم": 0.1,
    "مليمتر": 0.1,
    "مليمترات": 0.1,
    "cm": 1.0,
    "centimeter": 1.0,
    "centimeters": 1.0,
    "centimetre": 1.0,
    "centimetres": 1.0,
    "সেন্টিমিটার": 1.0,
    "সেমি": 1.0,
    "सेंटीमीटर": 1.0,
    "सेमी": 1.0,
    "centimetro": 1.0,
    "centimetros": 1.0,
    "centímetro": 1.0,
    "centímetros": 1.0,
    "centimètre": 1.0,
    "centimètres": 1.0,
    "سم": 1.0,
    "سنتيمتر": 1.0,
    "سنتيمترات": 1.0,
    "m": 100.0,
    "meter": 100.0,
    "meters": 100.0,
    "metre": 100.0,
    "metres": 100.0,
    "মিটার": 100.0,
    "मीटर": 100.0,
    "metro": 100.0,
    "metros": 100.0,
    "mètre": 100.0,
    "mètres": 100.0,
    "متر": 100.0,
    "أمتار": 100.0,
    "ft": 30.48,
    "foot": 30.48,
    "feet": 30.48,
    "ফুট": 30.48,
    "फुट": 30.48,
    "pie": 30.48,
    "pies": 30.48,
    "pied": 30.48,
    "pieds": 30.48,
    "قدم": 30.48,
    "in": 2.54,
    "inch": 2.54,
    "inches": 2.54,
    "ইঞ্চি": 2.54,
    "इंच": 2.54,
    "pulgada": 2.54,
    "pulgadas": 2.54,
    "pouce": 2.54,
    "pouces": 2.54,
    "بوصة": 2.54,
    "بوصات": 2.54,
}
_UNIT_PATTERN = "|".join(
    re.escape(unit) for unit in sorted(_UNIT_FACTORS, key=len, reverse=True)
)
_NUMBER = r"(?P<value>\d+(?:\.\d+)?)"
_DEPTH_PATTERN = re.compile(
    rf"(?<![\w.]){_NUMBER}\s*(?P<unit>{_UNIT_PATTERN})(?![\w])",
    re.IGNORECASE,
)

_QUALITATIVE_DEPTHS = (
    (
        re.compile(
            r"\b(?:chest(?:[- ]deep)?|up to (?:my )?chest)\b|"
            r"বুক(?:[- ]সমান| পর্যন্ত| অবধি)?|"
            r"(?:chest|buk|सीने|छाती|pecho|poitrine|الصدر)"
            r"(?:[- ]?(?:deep|সমান|পর্যন্ত|तक|hasta|jusqu.?à|حتى))?",
            re.IGNORECASE,
        ),
        120.0,
    ),
    (
        re.compile(
            r"\b(?:waist(?:[- ]deep)?|up to (?:my )?waist)\b|"
            r"কোমর(?:[- ]সমান| পর্যন্ত| অবধি)?|"
            r"(?:waist|komor|कमर|cintura|taille|الخصر)"
            r"(?:[- ]?(?:deep|সমান|পর্যন্ত|तक|hasta|jusqu.?à|حتى))?",
            re.IGNORECASE,
        ),
        90.0,
    ),
    (
        re.compile(
            r"\b(?:knee(?:[- ]deep|[- ]high)?|up to (?:my )?knees?)\b|"
            r"হাঁটু(?:[- ]?সমান|[- ]?পর্যন্ত|[- ]?অবধি|[- ]?গভীর)?|"
            r"(?:knee|hatu|घुटने|rodilla|genou|الركبة)"
            r"(?:[- ]?(?:deep|সমান|পর্যন্ত|तक|hasta|jusqu.?à|حتى))?",
            re.IGNORECASE,
        ),
        45.0,
    ),
    (
        re.compile(
            r"\b(?:ankle(?:[- ]deep)?|up to (?:my )?ankles?)\b|"
            r"গোড়ালি(?:[- ]?সমান| পর্যন্ত| অবধি)?|"
            r"গোড়ালি(?:[- ]?সমান| পর্যন্ত| অবধি)?|"
            r"(?:ankle|gorali|टखने|tobillo|cheville|الكاحل)"
            r"(?:[- ]?(?:deep|সমান|পর্যন্ত|तक|hasta|jusqu.?à|حتى))?",
            re.IGNORECASE,
        ),
        15.0,
    ),
)

_BLOCKED_PATTERN = re.compile(
    r"\b(?:closed|impassable|inaccessible)\b|"
    r"\b(?:cannot|can't) pass\b|\bno passage\b|"
    r"রাস্তা বন্ধ|পথ বন্ধ|চলাচল বন্ধ|যাতায়াত বন্ধ|যাতায়াত বন্ধ|"
    r"যাওয়া যাচ্ছে না|যাওয়া যাচ্ছে না|পেরোনো যাচ্ছে না|ডুবে গেছে|"
    r"रास्ता बंद|सड़क बंद|आवागमन बंद|पार नहीं|"
    r"cerrado|intransitable|no se puede pasar|"
    r"route fermée|impraticable|passage impossible|"
    r"مغلق|مغلقة|لا يمكن المرور",
    re.IGNORECASE,
)
_DIFFICULT_PATTERN = re.compile(
    r"\b(?:barely pass(?:es|ing|able)?|can barely|difficult to cross|"
    r"with difficulty)\b|কোনোমতে|কোনোমতে চলছে|কষ্টে যাচ্ছে|কষ্ট করে যাচ্ছে|"
    r"मुश्किल से पार|कठिनाई|difícil de cruzar|con dificultad|"
    r"difficile à traverser|صعب المرور",
    re.IGNORECASE,
)
_PASSABLE_PATTERN = re.compile(
    r"\b(?:passable|can pass|traffic (?:is )?moving|"
    r"vehicles? (?:can )?pass|rickshaw can go)\b|"
    r"চলাচল সম্ভব|চলাচল করছে|যানবাহন চলছে|গাড়ি চলছে|গাড়ি চলছে|"
    r"आवाजाही जारी|गाड़ी चल रही|पार कर सकते|"
    r"transitable|se puede pasar|vehículos pasan|"
    r"circulation possible|passable|يمكن المرور",
    re.IGNORECASE,
)
_DRY_PATTERN = re.compile(
    r"\b(?:no water|water has receded|water is gone|road is dry|dry road)\b|"
    r"পানি নেই|জল নেই|পানি নেমে গেছে|জল নেমে গেছে|রাস্তা শুকনো|"
    r"पानी नहीं|पानी उतर गया|सड़क सूखी|"
    r"sin agua|el agua bajó|calle seca|"
    r"pas d'eau|eau retirée|route sèche|"
    r"لا يوجد ماء|انحسر الماء",
    re.IGNORECASE,
)
_WATER_PATTERN = re.compile(
    r"\b(?:water|flood(?:ed|ing)?|inundat(?:ed|ion)|waterlogged)\b|"
    r"পানি|জল|বন্যা|জলাবদ্ধ|पानी|बाढ़|agua|inundación|eau|"
    r"inondation|ماء|فيضان",
    re.IGNORECASE,
)
_APPROXIMATE_PATTERN = re.compile(
    r"\b(?:about|around|approximately|approx\.?|roughly|nearly)\b|"
    r"প্রায়|প্রায়|আনুমানিক|মতো|करीब|लगभग|aproximadamente|environ|تقريبا",
    re.IGNORECASE,
)

_SEVERITY_ORDER = ("low", "moderate", "high", "severe")


def _normalized_text(text):
    normalized = "".join(
        str(unicodedata.decimal(character))
        if unicodedata.category(character) == "Nd"
        else character
        for character in text
    ).casefold()
    return re.sub(r"(?<=\d)[,٫](?=\d)", ".", normalized)


def _numeric_depths(text):
    depths = []
    for match in _DEPTH_PATTERN.finditer(text):
        value = float(match.group("value"))
        unit = match.group("unit").casefold()
        depths.append(value * _UNIT_FACTORS[unit])
    return depths


def _severity_for_depth(depth_cm):
    if depth_cm <= 15:
        return "low"
    if depth_cm <= 30:
        return "moderate"
    if depth_cm <= 60:
        return "high"
    return "severe"


def _more_severe(first, second):
    if first is None:
        return second
    if second is None:
        return first
    return max((first, second), key=_SEVERITY_ORDER.index)


def _access_severity(text):
    if _BLOCKED_PATTERN.search(text):
        return "severe"
    if _DIFFICULT_PATTERN.search(text):
        return "high"
    if _PASSABLE_PATTERN.search(text):
        return "low"
    return None


def parse_report(text):
    """Estimate flood depth and severity from a short free-form report."""
    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    if not text.strip():
        raise ValueError("text must not be empty.")

    normalized = _normalized_text(text)
    access_severity = _access_severity(normalized)

    if _DRY_PATTERN.search(normalized):
        return {
            "depth_cm": 0,
            "severity": _more_severe("low", access_severity),
            "confidence": 0.95,
            "needs_review": False,
        }

    numeric_depths = _numeric_depths(normalized)
    if numeric_depths:
        spread = max(numeric_depths) - min(numeric_depths)
        if spread > 10:
            depth_cm = None
            severity = _severity_for_depth(max(numeric_depths))
            confidence = 0.4
            needs_review = True
        else:
            depth_cm = round(sum(numeric_depths) / len(numeric_depths), 1)
            severity = _severity_for_depth(depth_cm)
            if len(numeric_depths) > 1:
                confidence = 0.8
                needs_review = True
            elif _APPROXIMATE_PATTERN.search(normalized):
                confidence = 0.8
                needs_review = True
            else:
                confidence = 0.95
                needs_review = False

        return {
            "depth_cm": depth_cm,
            "severity": _more_severe(severity, access_severity),
            "confidence": confidence,
            "needs_review": needs_review,
        }

    for pattern, estimated_depth in _QUALITATIVE_DEPTHS:
        if pattern.search(normalized):
            return {
                "depth_cm": estimated_depth,
                "severity": _more_severe(
                    _severity_for_depth(estimated_depth),
                    access_severity,
                ),
                "confidence": 0.65,
                "needs_review": True,
            }

    if access_severity is not None:
        return {
            "depth_cm": None,
            "severity": access_severity,
            "confidence": 0.75,
            "needs_review": True,
        }

    if _WATER_PATTERN.search(normalized):
        return {
            "depth_cm": None,
            "severity": "moderate",
            "confidence": 0.45,
            "needs_review": True,
        }

    return {
        "depth_cm": None,
        "severity": "unknown",
        "confidence": 0.0,
        "needs_review": True,
    }

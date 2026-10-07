import re

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w-])",
    re.IGNORECASE,
)
CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
CNPJ_PATTERN = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?(?:\d{4})-?\d{2}(?!\d)")
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?55[\s.-]?)?(?:\(?[1-9]\d\)?[\s.-]?)"
    r"(?:9\d{4}|\d{4})[-.\s]?\d{4}(?!\d)"
)
MOBILE_WITHOUT_AREA_PATTERN = re.compile(r"(?<!\d)9\d{4}[-.\s]?\d{4}(?!\d)")
DOCUMENT_PATTERN = re.compile(r"(?<!\d)\d{11,14}(?!\d)")

IPV4_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_PATTERN = re.compile(
    r"(?<![0-9A-F])(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}(?![0-9A-F])"
    r"|(?<![0-9A-F])(?:[0-9A-F]{4}\.){2}[0-9A-F]{4}(?![0-9A-F])",
    re.IGNORECASE,
)


def _protect_technical_identifiers(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = chr(0xE000 + len(protected))
        protected[token] = match.group(0)
        return token

    text = MAC_PATTERN.sub(replace, text)
    text = IPV4_PATTERN.sub(replace, text)
    return text, protected


def mask_personal_data(text: str) -> str:
    masked_text, protected = _protect_technical_identifiers(text)
    masked_text = EMAIL_PATTERN.sub("[E-MAIL]", masked_text)
    masked_text = CNPJ_PATTERN.sub("[CNPJ]", masked_text)
    masked_text = CPF_PATTERN.sub("[CPF]", masked_text)
    masked_text = PHONE_PATTERN.sub("[TELEFONE]", masked_text)
    masked_text = MOBILE_WITHOUT_AREA_PATTERN.sub("[TELEFONE]", masked_text)
    masked_text = DOCUMENT_PATTERN.sub("[DOCUMENTO]", masked_text)

    for token, original_value in protected.items():
        masked_text = masked_text.replace(token, original_value)

    return masked_text

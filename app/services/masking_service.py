import re

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w-])",
    re.IGNORECASE,
)
LABELED_CPF_PATTERN = re.compile(
    r"(?P<label>(?i:\bCPF\b)\s*[:#-]?\s*)"
    r"(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?!\d)"
)
FORMATTED_CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
LABELED_CNPJ_PATTERN = re.compile(
    r"(?P<label>(?i:\bCNPJ\b)\s*[:#-]?\s*)"
    r"(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)"
)
FORMATTED_CNPJ_PATTERN = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")
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
OPERATIONAL_ID_PATTERN = re.compile(
    r"(?i:\b(?:protocolo|contrato|chamado|ticket|OS)\b)"
    r"\s*(?:(?i:n(?:[º°o]|ro)?\.?)\s*)?(?:[:#-]\s*)?\d{1,20}\b"
)

NAME_WORD = (
    r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç]+"
    r"(?:[-'][A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç]+)?"
)
NAME_CONNECTOR = r"(?:da|de|do|das|dos|e)"
NAME_PATTERN = re.compile(
    r"(?P<prefix>"
    r"(?:(?i:\b(?:cliente|nome)\b)\s*:?\s*|(?i:\b(?:sr|sra)\.)\s*)"
    r")"
    rf"(?P<name>{NAME_WORD}(?:\s+(?:{NAME_CONNECTOR}\s+)?{NAME_WORD}){{0,3}})"
)


def _protect_preserved_values(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = chr(0xE000 + len(protected))
        protected[token] = match.group(0)
        return token

    text = OPERATIONAL_ID_PATTERN.sub(replace, text)
    text = MAC_PATTERN.sub(replace, text)
    text = IPV4_PATTERN.sub(replace, text)
    return text, protected


def _mask_labeled_value(match: re.Match[str], placeholder: str) -> str:
    return f"{match.group('label')}{placeholder}"


def _mask_name(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}[NOME]"


def mask_personal_data(text: str) -> str:
    """Mask supported PII.

    Addresses and names without a supported trigger remain unchanged because a
    regex-only heuristic cannot identify them reliably without excessive false
    positives.
    """
    masked_text, protected = _protect_preserved_values(text)
    masked_text = NAME_PATTERN.sub(_mask_name, masked_text)
    masked_text = EMAIL_PATTERN.sub("[E-MAIL]", masked_text)
    masked_text = LABELED_CNPJ_PATTERN.sub(
        lambda match: _mask_labeled_value(match, "[CNPJ]"),
        masked_text,
    )
    masked_text = FORMATTED_CNPJ_PATTERN.sub("[CNPJ]", masked_text)
    masked_text = LABELED_CPF_PATTERN.sub(
        lambda match: _mask_labeled_value(match, "[CPF]"),
        masked_text,
    )
    masked_text = FORMATTED_CPF_PATTERN.sub("[CPF]", masked_text)
    masked_text = DOCUMENT_PATTERN.sub("[DOCUMENTO]", masked_text)
    masked_text = PHONE_PATTERN.sub("[TELEFONE]", masked_text)
    masked_text = MOBILE_WITHOUT_AREA_PATTERN.sub("[TELEFONE]", masked_text)

    for token, original_value in protected.items():
        masked_text = masked_text.replace(token, original_value)

    return masked_text

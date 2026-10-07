from app.services.masking_service import mask_personal_data


def test_masks_personal_data() -> None:
    text = (
        "Cliente João, CPF 123.456.789-09, CNPJ 12.345.678/0001-90, "
        "e-mail joao.silva@example.com, telefone +55 (92) 99123-4567 e "
        "documento 123456789012."
    )

    masked = mask_personal_data(text)

    assert "123.456.789-09" not in masked
    assert "12.345.678/0001-90" not in masked
    assert "joao.silva@example.com" not in masked
    assert "+55 (92) 99123-4567" not in masked
    assert "123456789012" not in masked
    assert "Cliente [NOME]" in masked
    assert "[CPF]" in masked
    assert "[CNPJ]" in masked
    assert "[E-MAIL]" in masked
    assert "[TELEFONE]" in masked
    assert "[DOCUMENTO]" in masked


def test_preserves_network_and_signal_data() -> None:
    text = (
        "IP 192.168.100.1, MAC AA:BB:CC:DD:EE:FF, MAC Cisco aabb.ccdd.eeff, "
        "RSSI -67 dBm, SNR 31 dB, VLAN 203 e potência óptica -21,7 dBm."
    )

    assert mask_personal_data(text) == text


def test_masks_mobile_number_without_area_code() -> None:
    masked = mask_personal_data("Retorno pelo número 99123-4567.")

    assert masked == "Retorno pelo número [TELEFONE]."


def test_masks_email_followed_by_sentence_punctuation() -> None:
    masked = mask_personal_data("Contato maria.souza@exemplo.com.")

    assert masked == "Contato [E-MAIL]."


def test_preserves_operational_identifiers_and_technical_values() -> None:
    text = (
        "Contrato 4821937, protocolo 20261006001, ONU serial ALCLF1234567, "
        "porta 4, RSSI -79 dBm, potência óptica -27.5 dBm e teste de 280 Mbps."
    )

    masked = mask_personal_data(text)

    assert "Contrato 4821937" in masked
    assert "protocolo 20261006001" in masked
    assert "ONU serial ALCLF1234567" in masked
    assert "porta 4" in masked
    assert "-79 dBm" in masked
    assert "-27.5 dBm" in masked
    assert "280 Mbps" in masked


def test_preserves_each_supported_operational_identifier() -> None:
    text = (
        "protocolo 20261006001, contrato: 4821937, chamado nº 12345678901, "
        "os #98765432109 e ticket-45678901234."
    )

    assert mask_personal_data(text) == text


def test_distinguishes_cpf_from_generic_document_sequences() -> None:
    text = (
        "CPF 12345678909, CPF formatado 123.456.789-09, "
        "sequência 12345678909 e sequência longa 12345678901234."
    )

    masked = mask_personal_data(text)

    assert "CPF [CPF]" in masked
    assert "CPF formatado [CPF]" in masked
    assert "sequência [DOCUMENTO]" in masked
    assert "sequência longa [DOCUMENTO]" in masked


def test_masks_names_after_supported_triggers() -> None:
    text = (
        "Cliente Maria Souza, Sr. João da Silva, Sra. Ana Costa e "
        "nome: Carlos de Oliveira."
    )

    masked = mask_personal_data(text)

    assert "Cliente [NOME]" in masked
    assert "Sr. [NOME]" in masked
    assert "Sra. [NOME]" in masked
    assert "nome: [NOME]" in masked


def test_documents_known_name_and_address_limitations() -> None:
    text = "Maria Souza mora na Rua das Flores, 123."

    assert mask_personal_data(text) == text

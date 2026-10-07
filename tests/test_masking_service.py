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


def test_preserves_operational_identifiers_and_masks_document_like_protocol() -> None:
    text = (
        "Contrato 4821937, protocolo 20261006001, ONU serial ALCLF1234567, "
        "porta 4, RSSI -79 dBm, potência óptica -27.5 dBm e teste de 280 Mbps."
    )

    masked = mask_personal_data(text)

    assert "Contrato 4821937" in masked
    assert "20261006001" not in masked
    assert "protocolo [CPF]" in masked
    assert "ONU serial ALCLF1234567" in masked
    assert "porta 4" in masked
    assert "-79 dBm" in masked
    assert "-27.5 dBm" in masked
    assert "280 Mbps" in masked

import logging

import pytest

from scripts import try_llm


def test_show_masked_exits_without_building_llm_client(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_if_called() -> None:
        pytest.fail("LLMService não deve ser criado com --show-masked")

    monkeypatch.setattr(try_llm, "LLMService", fail_if_called)
    caplog.set_level(logging.INFO)

    try_llm.main(
        [
            "--text",
            (
                "CPF 123.456.789-09, tel (67) 99999-1234, "
                "e-mail maria.souza@exemplo.com, IP 100.64.12.35."
            ),
            "--show-masked",
        ]
    )

    output = caplog.messages[-1]
    assert "123.456.789-09" not in output
    assert "(67) 99999-1234" not in output
    assert "maria.souza@exemplo.com" not in output
    assert "[CPF]" in output
    assert "[TELEFONE]" in output
    assert "[E-MAIL]" in output
    assert "100.64.12.35" in output

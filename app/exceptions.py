class ApplicationError(Exception):
    status_code = 500
    default_message = "Ocorreu um erro interno. Tente novamente."

    def __init__(self, public_message: str | None = None) -> None:
        self.public_message = public_message or self.default_message
        super().__init__(self.public_message)


class InputValidationError(ApplicationError):
    status_code = 422
    default_message = "Revise os dados informados e tente novamente."


class LLMResponseError(ApplicationError):
    status_code = 502
    default_message = "A IA retornou uma resposta inválida. Tente novamente."


class LLMUnavailableError(ApplicationError):
    status_code = 503
    default_message = "O serviço de IA está indisponível. Tente novamente em instantes."

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.exceptions import ApplicationError

APP_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    application = FastAPI(title="NOC AI Assistant")
    application.mount(
        "/static",
        StaticFiles(directory=APP_DIR / "static"),
        name="static",
    )
    application.state.templates = Jinja2Templates(
        directory=APP_DIR / "templates",
    )

    @application.exception_handler(ApplicationError)
    async def application_error_handler(
        _request: Request,
        exception: ApplicationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": exception.public_message},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

"""Cookie de sesión: la única forma en que el navegador guarda la sesión."""

from dataclasses import dataclass

from fastapi import Request, Response


@dataclass(frozen=True, slots=True)
class SessionCookie:
    """HttpOnly (JavaScript no la lee), SameSite=Strict y, con HTTPS, prefijo __Host-."""

    name: str
    secure: bool
    max_age_seconds: int

    def set(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=self.name,
            value=token,
            max_age=self.max_age_seconds,
            path="/",
            secure=self.secure,
            httponly=True,
            samesite="strict",
        )

    def clear(self, response: Response) -> None:
        response.delete_cookie(
            key=self.name, path="/", secure=self.secure, httponly=True, samesite="strict"
        )

    def read(self, request: Request) -> str | None:
        return request.cookies.get(self.name)


def session_cookie(request: Request) -> SessionCookie:
    cookie = request.app.state.session_cookie
    if not isinstance(cookie, SessionCookie):
        msg = "SessionCookie no está configurada en app.state"
        raise TypeError(msg)
    return cookie

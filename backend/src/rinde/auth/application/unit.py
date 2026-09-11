"""Unidad de trabajo de autenticación: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.login import LoginUser
from rinde.auth.application.recover import RecoverAccount
from rinde.auth.application.register import RegisterUser
from rinde.auth.application.session_access import AuthenticateSession, LogoutUser
from rinde.auth.application.sessions import SessionIssuer


@dataclass(frozen=True, slots=True)
class AuthUnit:
    register: RegisterUser
    login: LoginUser
    logout: LogoutUser
    recover: RecoverAccount
    authenticate: AuthenticateSession


class AuthUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[AuthUnit]: ...


def build_auth_unit(deps: AuthDependencies) -> AuthUnit:
    issuer = SessionIssuer(deps)
    return AuthUnit(
        register=RegisterUser(deps, issuer),
        login=LoginUser(deps, issuer),
        logout=LogoutUser(deps),
        recover=RecoverAccount(deps, issuer),
        authenticate=AuthenticateSession(deps),
    )

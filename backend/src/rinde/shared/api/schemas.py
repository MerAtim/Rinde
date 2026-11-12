"""Esquemas web compartidos por todos los módulos."""

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

from rinde.shared.domain.money import Currency, Money


def decimal_text(value: Decimal) -> str:
    """Siempre en notación decimal, con la escala del valor.

    `str()` de un `Decimal` pasa a notación científica con los ceros chicos: un
    saldo cero en Bitcoin saldría como "0E-8" y no como "0.00000000".
    """
    return format(value, "f")


# El dinero sale como string: un número de JSON lo leería como `float` del otro lado.
AmountOut = Annotated[Decimal, PlainSerializer(decimal_text, return_type=str)]


def _decimal_from_string(value: object) -> Decimal:
    """Solo string: un número en JSON pasa por el `double` y ya perdió precisión."""
    if not isinstance(value, str):
        raise ValueError("el monto viaja como string decimal, no como número")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError("no es un monto decimal") from None


AmountIn = Annotated[
    Decimal,
    BeforeValidator(_decimal_from_string, json_schema_input_type=str),
    PlainSerializer(decimal_text, return_type=str),
    Field(description='Monto positivo como string decimal, por ejemplo "15300.50"'),
]


class ErrorResponse(BaseModel):
    """Toda respuesta de error: un código estable, nunca un mensaje traducido ni una traza."""

    code: str


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Documenta en OpenAPI qué códigos de error puede devolver un endpoint."""
    return {code: {"model": ErrorResponse} for code in status_codes}


class MoneyResponse(BaseModel):
    amount: AmountOut
    currency: Currency

    @classmethod
    def from_money(cls, money: Money) -> MoneyResponse:
        return cls(amount=money.amount, currency=money.currency)

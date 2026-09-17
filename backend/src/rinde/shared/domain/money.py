"""Dinero como objeto de valor (ADR-0002).

Reglas que este módulo hace cumplir, para que no dependan de la disciplina de
quien lo use:

* El monto es siempre `Decimal`. Un `float` no representa 0,10 exacto, y en una
  app de plata ese centavo perdido termina en un saldo que no cierra.
* Cada moneda tiene su precisión. Un monto con más decimales de los que admite
  su moneda es un error, no se redondea en silencio. Redondear es una decisión
  explícita (`Money.rounded`) y se toma en los bordes.
* No se operan monedas distintas. Pasar de una a otra es una conversión, con su
  cotización guardada, y eso no es una suma.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum

from rinde.shared.domain.errors import DomainError


class Currency(StrEnum):
    """Monedas admitidas. Sumar una es agregarla acá con su precisión."""

    ARS = "ARS"
    USD = "USD"
    BTC = "BTC"

    @property
    def minor_units(self) -> int:
        """Decimales que admite la moneda: 2 para ARS y USD, 8 para BTC (el satoshi)."""
        return _MINOR_UNITS[self]

    @property
    def quantum(self) -> Decimal:
        """La unidad mínima: 0.01 para ARS, 0.00000001 para BTC."""
        return Decimal(1).scaleb(-self.minor_units)


_MINOR_UNITS: dict[Currency, int] = {
    Currency.ARS: 2,
    Currency.USD: 2,
    Currency.BTC: 8,
}


class InvalidAmountError(DomainError):
    code = "AMOUNT_INVALID"


class AmountTooPreciseError(DomainError):
    code = "AMOUNT_TOO_PRECISE"


class CurrencyMismatchError(DomainError):
    code = "CURRENCY_MISMATCH"


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        # bool es subclase de int, y ninguno de los dos debería llegar hasta acá.
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise InvalidAmountError
        try:
            exact = self.amount.quantize(self.currency.quantum)
        except InvalidOperation:
            # El monto no entra en la precisión de la aritmética decimal.
            raise InvalidAmountError from None
        if exact != self.amount:
            raise AmountTooPreciseError
        # Mismo exponente para todos (1 y 1.00 se guardan igual) y sin cero negativo.
        object.__setattr__(self, "amount", exact.copy_abs() if exact.is_zero() else exact)

    @classmethod
    def rounded(cls, amount: Decimal, currency: Currency) -> Money:
        """Redondeo explícito, de banquero, para usar en los bordes.

        `ROUND_HALF_EVEN` lleva el medio al par más cercano. Así los redondeos de
        muchos montos no se inclinan siempre para el mismo lado.
        """
        if not isinstance(amount, Decimal) or not amount.is_finite():
            raise InvalidAmountError
        try:
            return cls(amount.quantize(currency.quantum, rounding=ROUND_HALF_EVEN), currency)
        except InvalidOperation:
            raise InvalidAmountError from None

    @classmethod
    def zero(cls, currency: Currency) -> Money:
        return cls(Decimal(0), currency)

    @classmethod
    def total(cls, items: Iterable[Money], currency: Currency) -> Money:
        """Suma una colección. Pide la moneda para que la suma de nada tenga una."""
        result = cls.zero(currency)
        for item in items:
            result += item
        return result

    @property
    def is_zero(self) -> bool:
        return self.amount.is_zero()

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    def _same_currency(self, other: Money) -> None:
        if self.currency is not other.currency:
            raise CurrencyMismatchError

    def __add__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount >= other.amount

    def __str__(self) -> str:
        """Para logs y depuración. El formato para personas lo hace el frontend."""
        return f"{self.currency} {self.amount}"

"""Esquemas de entrada y salida de importación.

El dinero viaja como string decimal (ADR-0002). El formato del CSV llega como
un campo JSON dentro del formulario que trae el archivo.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rinde.imports.application.use_cases import BatchPreview, Choice, Confirmation
from rinde.imports.domain.batch import LineStatus
from rinde.imports.domain.csv_layout import (
    MAX_COLUMN,
    CsvLayout,
    DateOrder,
    DebitCredit,
    DecimalMark,
    Delimiter,
    Encoding,
    SignedAmount,
)
from rinde.imports.domain.errors import ImportLayoutInvalidError
from rinde.imports.domain.statement import MAX_LINES, LineProblem
from rinde.shared.api.schemas import MoneyResponse
from rinde.shared.domain.money import Money

Column = Annotated[int, Field(ge=0, le=MAX_COLUMN)]


class SignedAmountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["signed"]
    column: Column


class DebitCreditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["debit_credit"]
    debit: Column
    credit: Column


class CsvLayoutRequest(BaseModel):
    """Cómo leer el CSV. Las columnas se cuentan desde cero."""

    model_config = ConfigDict(extra="forbid")

    delimiter: Delimiter
    encoding: Encoding
    decimal_mark: DecimalMark
    date_order: DateOrder
    has_header: bool
    date_column: Column
    description_column: Column
    amount: Annotated[SignedAmountRequest | DebitCreditRequest, Field(discriminator="kind")]

    @classmethod
    def parse(cls, raw: str) -> CsvLayout:
        """El campo del formulario: un error de forma es un formato inválido, con su código."""
        try:
            request = cls.model_validate_json(raw)
        except ValidationError as error:
            raise ImportLayoutInvalidError from error
        amount = request.amount
        return CsvLayout(
            delimiter=request.delimiter,
            encoding=request.encoding,
            decimal_mark=request.decimal_mark,
            date_order=request.date_order,
            has_header=request.has_header,
            date_column=request.date_column,
            description_column=request.description_column,
            amount=SignedAmount(amount.column)
            if isinstance(amount, SignedAmountRequest)
            else DebitCredit(amount.debit, amount.credit),
        )


class BatchLineResponse(BaseModel):
    number: int = Field(description="La línea en el archivo, contando el encabezado")
    occurred_on: date
    description: str | None
    amount: MoneyResponse = Field(description="Con signo: negativo es gasto")
    status: LineStatus = Field(
        description="new; duplicate, que ya entró y no se importa; "
        "possible_duplicate, que queda afuera salvo que se incluya"
    )
    category_id: UUID | None = Field(description="La categoría propuesta")
    rule: str | None = Field(
        description="El texto de la regla que la propuso; sin regla, es la de otros"
    )


class LineErrorResponse(BaseModel):
    line: int
    problem: LineProblem


class BatchResponse(BaseModel):
    id: UUID
    account_id: UUID
    file_name: str
    created_at: datetime
    expires_at: datetime
    confirmed: bool
    lines: list[BatchLineResponse]
    errors: list[LineErrorResponse] = Field(description="Las líneas que no se pudieron leer")

    @classmethod
    def from_preview(cls, preview: BatchPreview) -> BatchResponse:
        batch = preview.batch
        return cls(
            id=batch.id,
            account_id=batch.account_id,
            file_name=batch.file_name,
            created_at=batch.created_at,
            expires_at=batch.expires_at,
            confirmed=batch.confirmed_at is not None,
            lines=[
                BatchLineResponse(
                    number=line.number,
                    occurred_on=line.occurred_on,
                    description=line.description,
                    amount=MoneyResponse.from_money(Money(line.signed_amount, batch.currency)),
                    status=line.status,
                    category_id=preview.suggestions[line.number].category_id,
                    rule=preview.suggestions[line.number].rule,
                )
                for line in batch.lines
            ],
            errors=[
                LineErrorResponse(line=error.number, problem=error.problem)
                for error in batch.errors
            ],
        )


class ChoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    category_id: UUID
    remember: str | None = Field(
        default=None,
        max_length=120,
        description="Un texto para recordar esta categoría en las próximas importaciones",
    )


class ConfirmRequest(BaseModel):
    """Las líneas que entran, cada una con su categoría. Las que no figuran quedan afuera."""

    model_config = ConfigDict(extra="forbid")

    lines: list[ChoiceRequest] = Field(max_length=MAX_LINES)

    def choices(self) -> list[Choice]:
        return [Choice(item.number, item.category_id, item.remember) for item in self.lines]


class ConfirmResponse(BaseModel):
    imported: int
    skipped: int = Field(description="Las que ya habían entrado: confirmar de nuevo no duplica")

    @classmethod
    def from_confirmation(cls, confirmation: Confirmation) -> ConfirmResponse:
        return cls(imported=confirmation.imported, skipped=confirmation.skipped)

"""Errores de presupuestos. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class BudgetError(DomainError):
    code = "BUDGET_ERROR"


class BudgetNotFoundError(BudgetError):
    """La categoría no tiene un tope vigente este mes: no hay nada que quitar."""

    code = "BUDGET_NOT_FOUND"


class BudgetCategoryNotFoundError(BudgetError):
    """No existe, o es de otra persona: las dos se responden igual (ADR-0009)."""

    code = "BUDGET_CATEGORY_NOT_FOUND"


class BudgetCategoryNotExpenseError(BudgetError):
    """Un ingreso no se presupuesta: el tope es de lo que sale."""

    code = "BUDGET_CATEGORY_NOT_EXPENSE"


class BudgetAmountInvalidError(BudgetError):
    """Un tope de cero o negativo no mide nada."""

    code = "BUDGET_AMOUNT_INVALID"


class BudgetCurrencyNotAllowedError(BudgetError):
    """Bitcoin no puede ser la moneda del tope: no tiene cotización (ADR-0017)."""

    code = "BUDGET_CURRENCY_NOT_ALLOWED"


class BudgetMonthInvalidError(BudgetError):
    """Un mes que todavía no empezó no tiene gasto que medir."""

    code = "BUDGET_MONTH_INVALID"

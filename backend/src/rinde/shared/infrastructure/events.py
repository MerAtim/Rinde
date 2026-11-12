"""Bus de eventos en el proceso (ADR-0022).

Un módulo publica un hecho por un puerto, sin saber quién lo escucha; la raíz
de composición suscribe a los interesados. Se publica después de confirmar la
transacción que produjo el hecho, así que un suscriptor que falla no puede
deshacerlo: la falla queda en el log y el pedido sigue.
"""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, cast

logger = logging.getLogger(__name__)

type Handler[E] = Callable[[E], Awaitable[None]]


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: defaultdict[type[Any], list[Handler[Any]]] = defaultdict(list)

    def subscribe[E](self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        """Llama a cada suscriptor en el orden en que se suscribió, uno por vez."""
        for handler in self._handlers.get(type(event), []):
            try:
                await cast("Handler[object]", handler)(event)
            # Cualquier falla de un suscriptor: el hecho ya está confirmado, y
            # cortar acá haría que el cliente reintente algo que sí ocurrió.
            # La cancelación del pedido no es Exception, así que sí se propaga.
            except Exception:
                logger.exception(
                    "Falló un suscriptor de eventos",
                    extra={"event": type(event).__name__, "handler": _name(handler)},
                )


def _name(handler: Handler[Any]) -> str:
    return getattr(handler, "__qualname__", type(handler).__qualname__)

"""Normalización del texto que escribe una persona: nombres, descripciones.

Lo usan todos los módulos para que "Nación" escrito de dos formas distintas sea
el mismo texto, y para que no entren caracteres que no se ven en pantalla.
"""

import unicodedata

# Categorías Unicode de control y de formato: no se ven, pero hacen que dos
# textos que parecen iguales no lo sean.
_INVISIBLE = {"Cc", "Cf"}


def normalize(raw: str) -> str:
    """NFC y sin espacios en los bordes. No valida: para eso está `is_clean`."""
    return unicodedata.normalize("NFC", raw).strip()


def is_clean(value: str) -> bool:
    """Si el texto no trae caracteres invisibles."""
    return not any(unicodedata.category(char) in _INVISIBLE for char in value)

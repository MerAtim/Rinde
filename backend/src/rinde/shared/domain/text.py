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


def fold(value: str) -> str:
    """La forma comparable de un texto: sin tildes y en minúsculas.

    Sirve para buscar. Nadie escribe los acentos en un buscador, así que
    "panaderia" tiene que encontrar "panadería". Se pliega todo, la eñe
    incluida, igual que hace `unaccent` en PostgreSQL: como lo escrito y lo
    buscado se pliegan de la misma forma, buscar "año" también funciona.

    Se hace acá y no con una extensión de la base para que la búsqueda ande
    igual en cualquier PostgreSQL, sin depender de qué extensiones permita el
    proveedor.
    """
    descompuesto = unicodedata.normalize("NFD", value)
    sin_marcas = "".join(char for char in descompuesto if not unicodedata.combining(char))
    return sin_marcas.casefold()

"""El kernel de texto: normalizar lo que escribe una persona y plegarlo para buscar."""

import pytest

from rinde.shared.domain.text import fold, is_clean, normalize


class TestNormalizar:
    def test_saca_los_espacios_de_los_bordes(self) -> None:
        assert normalize("  Galicia sueldo  ") == "Galicia sueldo"

    def test_deja_una_sola_forma_para_el_mismo_texto(self) -> None:
        """La "a" con tilde se puede escribir de dos formas; NFC deja una sola."""
        compuesta = "café"
        descompuesta = "café"

        assert compuesta != descompuesta
        assert normalize(compuesta) == normalize(descompuesta)


class TestCaracteresInvisibles:
    def test_un_texto_comun_pasa(self) -> None:
        assert is_clean("Galicia sueldo")

    @pytest.mark.parametrize(
        "invisible",
        [
            "\u200b",  # espacio de ancho cero
            "\u200e",  # marca de izquierda a derecha
            "\x00",  # nulo
        ],
    )
    def test_rechaza_lo_que_no_se_ve(self, invisible: str) -> None:
        assert not is_clean(f"Galicia{invisible}sueldo")


class TestPlegarParaBuscar:
    @pytest.mark.parametrize(
        ("escrito", "buscado"),
        [
            ("panadería", "panaderia"),
            ("PANADERÍA", "panaderia"),
            ("Almacén", "almacen"),
            ("Ñandú", "nandu"),
        ],
    )
    def test_encuentra_sin_tildes_ni_mayusculas(self, escrito: str, buscado: str) -> None:
        assert fold(escrito) == fold(buscado)

    def test_lo_escrito_con_tilde_tambien_se_encuentra_con_tilde(self) -> None:
        """Se pliegan los dos lados, así que buscar con acento sigue andando."""
        assert fold("panadería") == fold("Panadería")

    def test_no_junta_textos_distintos(self) -> None:
        assert fold("panadería") != fold("carniceria")

    def test_deja_los_numeros_y_los_espacios_como_estan(self) -> None:
        assert fold("Coto 15 de mayo") == "coto 15 de mayo"

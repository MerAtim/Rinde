// Aplica el tema antes del primer pintado, para que no haya un destello de colores.
// Oscuro por defecto (decisión de producto, ADR-0006); claro solo si el usuario lo eligió.
// Es un archivo propio y no un script en línea porque la CSP solo permite script-src 'self'.
(function () {
  var theme = "dark";
  try {
    if (localStorage.getItem("rinde.theme") === "light") {
      theme = "light";
    }
  } catch (error) {
    // Almacenamiento no disponible (modo privado): queda el tema por defecto.
  }
  document.documentElement.dataset.theme = theme;
})();

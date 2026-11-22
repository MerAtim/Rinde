/**
 * Guarda un archivo armado en el navegador, como si se descargara. El enlace
 * temporal se libera enseguida: el contenido no queda en memoria.
 */
export function saveFile(fileName: string, content: Blob): void {
  const url = URL.createObjectURL(content);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

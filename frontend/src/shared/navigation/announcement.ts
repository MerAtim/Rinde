/**
 * Un aviso que una pantalla deja para la siguiente al navegar, como "Abriste la
 * cuenta Galicia". Viaja en el estado del historial y lo muestra la región
 * `status` del marco de la app, que no se desmonta al cambiar de pantalla: por
 * eso el lector de pantalla lo anuncia.
 */
export interface AnnouncementState {
  announcement: string;
}

export function withAnnouncement(announcement: string): AnnouncementState {
  return { announcement };
}

/** El estado del historial puede venir de cualquier lado: se valida antes de mostrarlo. */
export function announcementFrom(state: unknown): string {
  if (
    typeof state === "object" &&
    state !== null &&
    "announcement" in state &&
    typeof state.announcement === "string"
  ) {
    return state.announcement;
  }
  return "";
}

import { useCallback, useSyncExternalStore } from "react";

/**
 * Si la consulta de medios coincide, y se actualiza cuando cambia. Para decidir
 * qué se renderiza; lo que solo cambia el aspecto va en CSS.
 *
 * Sin `matchMedia` (jsdom, navegadores muy viejos) responde `fallback`.
 */
export function useMediaQuery(query: string, fallback = true): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window.matchMedia !== "function") {
        return () => undefined;
      }
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => {
        list.removeEventListener("change", onChange);
      };
    },
    [query],
  );

  return useSyncExternalStore(
    subscribe,
    () => (typeof window.matchMedia === "function" ? window.matchMedia(query).matches : fallback),
    () => fallback,
  );
}

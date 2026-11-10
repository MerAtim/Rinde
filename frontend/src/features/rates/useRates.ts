import { skipToken, useQuery } from "@tanstack/react-query";

import { type ConversionInput, fetchConversion, fetchTodayRates } from "./api";

export const rateKeys = {
  all: ["rates"] as const,
  today: () => [...rateKeys.all, "today"] as const,
};

// El servidor guarda lo que trae de las fuentes durante 15 minutos: pedir más
// seguido no trae nada nuevo.
const FIVE_MINUTES = 5 * 60_000;

export function useTodayRates() {
  return useQuery({
    queryKey: rateKeys.today(),
    queryFn: ({ signal }) => fetchTodayRates(signal),
    staleTime: FIVE_MINUTES,
  });
}

/** El equivalente de un monto en la otra moneda. Sin datos (`null`), no pide nada. */
export function useConversion(input: ConversionInput | null) {
  return useQuery({
    queryKey: [...rateKeys.all, "conversion", input] as const,
    // `skipToken`: sin datos la consulta no existe, en vez de quedar deshabilitada.
    queryFn: input ? ({ signal }) => fetchConversion(input, signal) : skipToken,
    staleTime: FIVE_MINUTES,
  });
}

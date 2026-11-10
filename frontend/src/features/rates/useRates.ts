import { useQuery } from "@tanstack/react-query";

import { fetchTodayRates } from "./api";

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

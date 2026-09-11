import { useQuery } from "@tanstack/react-query";

import { fetchReadiness } from "../../shared/api/client";

const THIRTY_SECONDS = 30_000;

export function useReadiness() {
  return useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: THIRTY_SECONDS,
  });
}

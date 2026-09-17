import { QueryObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { SESSION_QUERY_KEY } from "./features/auth/useSession";
import { createQueryClient } from "./queryClient";
import { ApiRequestError } from "./shared/api/http";

describe("Cliente de datos", () => {
  it("descarta la sesión cuando un pedido informa que terminó", async () => {
    const client = createQueryClient({ queries: { retry: false } });
    client.setQueryData(SESSION_QUERY_KEY, { username: "mechi" });

    await client
      .query({
        queryKey: ["accounts"],
        queryFn: () => Promise.reject(new ApiRequestError("NOT_AUTHENTICATED", 401)),
      })
      .catch(() => undefined);

    expect(client.getQueryData(SESSION_QUERY_KEY)).toBeNull();
  });

  it("conserva la sesión ante otros errores", async () => {
    const client = createQueryClient({ queries: { retry: false } });
    client.setQueryData(SESSION_QUERY_KEY, { username: "mechi" });

    await client
      .query({
        queryKey: ["accounts"],
        queryFn: () => Promise.reject(new ApiRequestError("ACCOUNT_NOT_FOUND", 404)),
      })
      .catch(() => undefined);

    expect(client.getQueryData(SESSION_QUERY_KEY)).toEqual({ username: "mechi" });
  });

  it("no reintenta un error 4xx, pero sí uno de red", async () => {
    const client = createQueryClient({ queries: { retryDelay: 0 } });
    const notFound = vi.fn(() => Promise.reject(new ApiRequestError("ACCOUNT_NOT_FOUND", 404)));
    const offline = vi.fn(() => Promise.reject(new ApiRequestError("NETWORK_ERROR", 0)));

    for (const [key, queryFn] of [
      ["a", notFound],
      ["b", offline],
    ] as const) {
      const observer = new QueryObserver(client, { queryKey: [key], queryFn });
      await new Promise<void>((resolve) => {
        const unsubscribe = observer.subscribe((result) => {
          if (result.isError) {
            unsubscribe();
            resolve();
          }
        });
      });
    }

    expect(notFound).toHaveBeenCalledTimes(1);
    expect(offline).toHaveBeenCalledTimes(4);
  });
});

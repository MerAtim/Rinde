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

  it("al cambiar quién está en la sesión, olvida los datos de la persona anterior", () => {
    const client = createQueryClient();
    const demo = { username: "demo-k3v9q2m7xa", demo_expires_at: "2026-11-15T20:30:00Z" };
    client.setQueryData(SESSION_QUERY_KEY, demo);
    client.setQueryData(["accounts"], ["cuenta de la demo"]);

    // La misma persona, con la sesión recargada: nada se pierde.
    client.setQueryData(SESSION_QUERY_KEY, { ...demo });
    expect(client.getQueryData(["accounts"])).toEqual(["cuenta de la demo"]);

    client.setQueryData(SESSION_QUERY_KEY, { username: "mechi", demo_expires_at: null });
    expect(client.getQueryData(["accounts"])).toBeUndefined();

    client.setQueryData(["accounts"], ["cuenta de mechi"]);
    client.setQueryData(SESSION_QUERY_KEY, null);
    expect(client.getQueryData(["accounts"])).toBeUndefined();
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

import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import { accountKeys } from "../accounts/useAccounts";
import { transactionKeys } from "../transactions/useTransactions";
import {
  deleteTransfer,
  type Transfer,
  type TransferFilters,
  type TransferInput,
  type TransferPage,
  fetchTransfers,
  registerTransfer,
  restoreTransfer,
} from "./api";

export const transferKeys = {
  all: ["transfers"] as const,
  lists: () => [...transferKeys.all, "list"] as const,
  list: (filters: TransferFilters) => [...transferKeys.lists(), filters] as const,
};

/** La lista crece con "Ver más": cada página trae el cursor de la siguiente. */
export function useTransfers(filters: TransferFilters = {}) {
  return useInfiniteQuery({
    queryKey: transferKeys.list(filters),
    queryFn: ({ pageParam, signal }) =>
      fetchTransfers({ ...filters, ...(pageParam ? { cursor: pageParam } : {}) }, signal),
    initialPageParam: "",
    getNextPageParam: (page: TransferPage) => page.next_cursor ?? undefined,
  });
}

/** Todas las transferencias ya traídas, en una sola lista. */
export function flattenTransfers(data: InfiniteData<TransferPage> | undefined): Transfer[] {
  return data ? data.pages.flatMap((page) => page.items) : [];
}

/**
 * Una transferencia cambia su propia lista y los saldos, que viven en otra
 * consulta y en otro módulo: el saldo suma movimientos y transferencias
 * (ADR-0014, decisión 1).
 */
function useInvalidateMoney() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: transferKeys.all }),
      queryClient.invalidateQueries({ queryKey: transactionKeys.all }),
      queryClient.invalidateQueries({ queryKey: accountKeys.all }),
    ]);
}

export function useRegisterTransfer() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: TransferInput; idempotencyKey: string }) =>
      registerTransfer(input, idempotencyKey),
    onSuccess: invalidate,
  });
}

export function useDeleteTransfer() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (id: string) => deleteTransfer(id),
    onSuccess: invalidate,
  });
}

export function useRestoreTransfer() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (id: string) => restoreTransfer(id),
    onSuccess: invalidate,
  });
}

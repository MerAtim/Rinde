import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { accountKeys } from "../accounts/useAccounts";
import {
  type Balance,
  deleteTransaction,
  editTransaction,
  fetchBalances,
  fetchCategories,
  fetchHistory,
  fetchTransactions,
  registerTransaction,
  restoreTransaction,
  type HistoryEntry,
  type HistoryPage,
  type Transaction,
  type TransactionFilters,
  type TransactionInput,
  type TransactionPage,
} from "./api";

export const transactionKeys = {
  all: ["transactions"] as const,
  lists: () => [...transactionKeys.all, "list"] as const,
  list: (filters: TransactionFilters) => [...transactionKeys.lists(), filters] as const,
  balances: () => [...transactionKeys.all, "balances"] as const,
  history: (filters: TransactionFilters) => [...transactionKeys.all, "history", filters] as const,
  categories: () => ["categories"] as const,
};

/** La lista crece con "Ver más": cada página trae el cursor de la siguiente. */
export function useTransactions(filters: TransactionFilters = {}) {
  return useInfiniteQuery({
    queryKey: transactionKeys.list(filters),
    queryFn: ({ pageParam, signal }) =>
      fetchTransactions({ ...filters, ...(pageParam ? { cursor: pageParam } : {}) }, signal),
    initialPageParam: "",
    getNextPageParam: (page: TransactionPage) => page.next_cursor ?? undefined,
  });
}

/** Todos los movimientos ya traídos, en una sola lista. */
export function flatten(data: InfiniteData<TransactionPage> | undefined): Transaction[] {
  return data ? data.pages.flatMap((page) => page.items) : [];
}

/** Movimientos y transferencias en una sola lista, paginada con el mismo cursor. */
export function useHistory(filters: TransactionFilters = {}) {
  return useInfiniteQuery({
    queryKey: transactionKeys.history(filters),
    queryFn: ({ pageParam, signal }) =>
      fetchHistory({ ...filters, ...(pageParam ? { cursor: pageParam } : {}) }, signal),
    initialPageParam: "",
    getNextPageParam: (page: HistoryPage) => page.next_cursor ?? undefined,
  });
}

/** Todo lo ya traído, en una sola lista. */
export function flattenHistory(data: InfiniteData<HistoryPage> | undefined): HistoryEntry[] {
  return data ? data.pages.flatMap((page) => page.items) : [];
}

export function useBalances() {
  return useQuery({
    queryKey: transactionKeys.balances(),
    queryFn: ({ signal }) => fetchBalances(signal),
  });
}

/** El saldo de cada cuenta, por identificador, para juntarlo con la lista de cuentas. */
export function balancesById(balances: Balance[] | undefined): Map<string, Balance> {
  return new Map((balances ?? []).map((balance) => [balance.account_id, balance]));
}

export function useCategories() {
  return useQuery({
    queryKey: transactionKeys.categories(),
    queryFn: ({ signal }) => fetchCategories(signal),
    // Cambian poco y las necesita cada formulario.
    staleTime: 5 * 60_000,
  });
}

/** Un movimiento nuevo cambia listas y saldos, y el saldo vive en otra consulta. */
function useInvalidateMoney() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: transactionKeys.all }),
      queryClient.invalidateQueries({ queryKey: accountKeys.all }),
    ]);
}

export function useRegisterTransaction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: TransactionInput; idempotencyKey: string }) =>
      registerTransaction(input, idempotencyKey),
    onSuccess: invalidate,
  });
}

export function useEditTransaction(id: string) {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (input: Omit<TransactionInput, "account_id">) => editTransaction(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteTransaction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (id: string) => deleteTransaction(id),
    onSuccess: invalidate,
  });
}

export function useRestoreTransaction() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (id: string) => restoreTransaction(id),
    onSuccess: invalidate,
  });
}

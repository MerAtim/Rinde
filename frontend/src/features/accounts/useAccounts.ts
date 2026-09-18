import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Account,
  archiveAccount,
  fetchAccount,
  fetchAccounts,
  openAccount,
  type OpenAccountInput,
  renameAccount,
} from "./api";

export const accountKeys = {
  all: ["accounts"] as const,
  lists: () => [...accountKeys.all, "list"] as const,
  list: (includeArchived: boolean) => [...accountKeys.lists(), { includeArchived }] as const,
  detail: (id: string) => [...accountKeys.all, "detail", id] as const,
};

export function useAccounts(includeArchived: boolean) {
  return useQuery({
    queryKey: accountKeys.list(includeArchived),
    queryFn: ({ signal }) => fetchAccounts(includeArchived, signal),
  });
}

export function useAccount(id: string) {
  return useQuery({
    queryKey: accountKeys.detail(id),
    queryFn: ({ signal }) => fetchAccount(id, signal),
  });
}

/**
 * Abrir no es optimista, a diferencia de renombrar: el identificador lo genera
 * el servidor, y si rechaza el nombre la persona tiene que seguir en el
 * formulario para corregirlo, no ver aparecer y desaparecer una cuenta.
 */
export function useOpenAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: OpenAccountInput) => openAccount(input),
    onSuccess: async (account) => {
      queryClient.setQueryData(accountKeys.detail(account.id), account);
      await queryClient.invalidateQueries({ queryKey: accountKeys.lists() });
    },
  });
}

/** Optimista: el nombre cambia en pantalla al instante y vuelve atrás si el servidor lo rechaza. */
export function useRenameAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => renameAccount(id, name),
    onMutate: async (name) => {
      await queryClient.cancelQueries({ queryKey: accountKeys.detail(id) });
      const previous = queryClient.getQueryData<Account>(accountKeys.detail(id));
      if (previous) {
        queryClient.setQueryData<Account>(accountKeys.detail(id), { ...previous, name });
      }
      return { previous };
    },
    onError: (_error, _name, context) => {
      if (context?.previous) {
        queryClient.setQueryData(accountKeys.detail(id), context.previous);
      }
    },
    onSuccess: (account) => {
      queryClient.setQueryData(accountKeys.detail(id), account);
    },
    // Con éxito o sin él, se vuelve a leer: la cuenta pudo cambiar en otra pestaña (por ejemplo, archivarse).
    onSettled: () => queryClient.invalidateQueries({ queryKey: accountKeys.all }),
  });
}

export function useArchiveAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => archiveAccount(id),
    onSuccess: async (account) => {
      queryClient.setQueryData(accountKeys.detail(id), account);
      await queryClient.invalidateQueries({ queryKey: accountKeys.lists() });
    },
  });
}

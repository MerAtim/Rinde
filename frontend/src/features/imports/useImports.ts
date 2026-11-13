import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useInvalidateMoney } from "../transactions/useTransactions";
import {
  type Choice,
  confirmBatch,
  type CsvLayout,
  discardBatch,
  fetchBatch,
  uploadBatch,
} from "./api";

const batchKey = (id: string) => ["imports", id] as const;

export function useBatch(id: string) {
  return useQuery({
    queryKey: batchKey(id),
    queryFn: ({ signal }) => fetchBatch(id, signal),
  });
}

export function useUploadBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      file,
      layout,
    }: {
      accountId: string;
      file: File;
      layout: CsvLayout;
    }) => uploadBatch(accountId, file, layout),
    // La vista previa que devuelve es la misma que la pantalla va a pedir.
    onSuccess: (batch) => {
      queryClient.setQueryData(batchKey(batch.id), batch);
    },
  });
}

/** Lo importado cambia listas, saldos, el dashboard, presupuestos y alertas. */
export function useConfirmBatch(id: string) {
  const queryClient = useQueryClient();
  const invalidateMoney = useInvalidateMoney();
  return useMutation({
    mutationFn: (lines: Choice[]) => confirmBatch(id, lines),
    onSuccess: () =>
      Promise.all([invalidateMoney(), queryClient.invalidateQueries({ queryKey: batchKey(id) })]),
  });
}

export function useDiscardBatch(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => discardBatch(id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: batchKey(id) });
    },
  });
}

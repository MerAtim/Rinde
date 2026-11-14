import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useInvalidateMoney } from "../transactions/useTransactions";
import {
  cancelRule,
  changeRule,
  createRule,
  fetchRules,
  generateDue,
  type RuleChange,
  type RuleInput,
} from "./api";
import { recurringKeys } from "./keys";

export function useRules() {
  return useQuery({
    queryKey: recurringKeys.all,
    queryFn: ({ signal }) => fetchRules(signal),
  });
}

/** Una regla que empezó antes de hoy trae movimientos: cambia saldos, listas y presupuestos. */
export function useCreateRule() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: RuleInput; idempotencyKey: string }) =>
      createRule(input, idempotencyKey),
    onSuccess: invalidate,
  });
}

/** Antes de cambiar el monto el servidor genera lo vencido (ADR-0027): también cambia saldos. */
export function useChangeRule(id: string) {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (change: RuleChange) => changeRule(id, change),
    onSuccess: invalidate,
  });
}

export function useCancelRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelRule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: recurringKeys.all }),
  });
}

/**
 * Al abrir la app, lo recurrente que venció se vuelve movimiento (ADR-0027),
 * igual que las cuotas. Si falla no se avisa: se genera la próxima vez, con su
 * fecha. Si generó algo, se recargan las cuentas y los resúmenes.
 */
export function useGenerateDueRecurring() {
  const invalidate = useInvalidateMoney();
  const { mutate } = useMutation({
    mutationFn: generateDue,
    onSuccess: async ({ created }) => {
      if (created > 0) {
        await invalidate();
      }
    },
  });
  useEffect(() => {
    mutate();
  }, [mutate]);
}

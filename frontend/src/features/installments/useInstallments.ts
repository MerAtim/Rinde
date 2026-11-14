import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useInvalidateMoney } from "../transactions/useTransactions";
import { cancelPlan, createPlan, fetchPlans, generateDue, type PlanInput } from "./api";
import { installmentKeys } from "./keys";

export function usePlans() {
  return useQuery({
    queryKey: installmentKeys.all,
    queryFn: ({ signal }) => fetchPlans(signal),
  });
}

/** Una compra nueva puede traer cuotas vencidas: cambia saldos, listas y presupuestos. */
export function useCreatePlan() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: PlanInput; idempotencyKey: string }) =>
      createPlan(input, idempotencyKey),
    onSuccess: invalidate,
  });
}

export function useCancelPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelPlan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: installmentKeys.all }),
  });
}

/**
 * Al abrir la app, las cuotas que vencieron se vuelven movimientos (ADR-0026).
 *
 * El hosting no tiene tareas programadas: lo pide la pantalla, una vez por
 * sesión. Si falla no se avisa, porque no se pierde nada: se genera la próxima
 * vez, con su fecha. Si generó algo, se recargan las cuentas y los resúmenes.
 */
export function useGenerateDueInstallments() {
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

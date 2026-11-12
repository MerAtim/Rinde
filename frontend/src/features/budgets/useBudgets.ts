import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type BudgetInput, fetchBudgets, removeBudget, setBudget } from "./api";
import { budgetKeys } from "./keys";

export function useBudgets(month: string | null) {
  return useQuery({
    queryKey: budgetKeys.month(month),
    queryFn: ({ signal }) => fetchBudgets(month, signal),
    // Al cambiar de mes queda el anterior a la vista mientras llega el nuevo.
    placeholderData: keepPreviousData,
  });
}

/** Fijar o quitar un tope cambia el mes en curso; los pasados quedan como estaban. */
function useInvalidateBudgets() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: budgetKeys.all });
}

export function useSetBudget() {
  const invalidate = useInvalidateBudgets();
  return useMutation({
    mutationFn: ({ categoryId, input }: { categoryId: string; input: BudgetInput }) =>
      setBudget(categoryId, input),
    onSuccess: invalidate,
  });
}

export function useRemoveBudget() {
  const invalidate = useInvalidateBudgets();
  return useMutation({
    mutationFn: (categoryId: string) => removeBudget(categoryId),
    onSuccess: invalidate,
  });
}

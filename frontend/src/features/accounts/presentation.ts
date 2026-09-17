import type { IconName } from "../../shared/ui/Icon";
import type { AccountKind } from "./api";

export const KIND_ICON: Record<AccountKind, IconName> = {
  cash: "cash",
  bank: "bank",
  credit_card: "credit-card",
  crypto_wallet: "bitcoin",
};

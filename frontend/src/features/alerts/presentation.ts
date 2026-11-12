import type { StatusTone } from "../../shared/ui/StatusChip";
import type { IconName } from "../../shared/ui/Icon";
import type { AlertThreshold } from "./api";

/** Los mismos tonos e íconos que el estado del presupuesto: el 80 % avisa, el 100 % es error. */
export const THRESHOLD: Record<AlertThreshold, { tone: StatusTone; icon: IconName }> = {
  warning: { tone: "warning", icon: "warning" },
  over: { tone: "error", icon: "error" },
};

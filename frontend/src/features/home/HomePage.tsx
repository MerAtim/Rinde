import { cx } from "../../shared/ui/cx";
import { Dashboard } from "../dashboard/Dashboard";
import { HealthStatus } from "../health/HealthStatus";
import { RatesPanel } from "../rates/RatesPanel";
import styles from "./HomePage.module.css";

/** El inicio: primero el resumen propio; después, el dólar del día como contexto. */
export function HomePage() {
  return (
    <div className={cx(styles.page)}>
      <Dashboard />
      <RatesPanel />
      <HealthStatus />
    </div>
  );
}

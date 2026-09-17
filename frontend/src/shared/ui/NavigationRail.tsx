import { NavLink } from "react-router";

import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";
import styles from "./NavigationRail.module.css";

export interface Destination {
  to: string;
  label: string;
  icon: IconName;
  /** Versión rellena del ícono: marca el destino actual además del indicador y el texto. */
  activeIcon: IconName;
  /** Solo activo en la ruta exacta; para el inicio, que si no estaría activo en todas. */
  end?: boolean;
}

interface NavigationRailProps {
  label: string;
  destinations: readonly Destination[];
}

/**
 * Navegación principal de Material 3: rail de 88 px al costado y, en pantallas
 * chicas, barra inferior. Son enlaces comunes: el destino actual lleva
 * `aria-current="page"`, que es lo que anuncia un lector de pantalla.
 */
export function NavigationRail({ label, destinations }: NavigationRailProps) {
  return (
    <nav aria-label={label} className={cx(styles.rail)}>
      <ul className={cx(styles.list)}>
        {destinations.map((destination) => (
          <li key={destination.to}>
            <NavLink to={destination.to} end={destination.end ?? false} className={cx(styles.item)}>
              {({ isActive }) => (
                <>
                  <span className={cx("state-layer", styles.indicator)}>
                    <Icon name={isActive ? destination.activeIcon : destination.icon} size={24} />
                  </span>
                  <span className={cx(styles.label)}>{destination.label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

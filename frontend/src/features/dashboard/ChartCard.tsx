import { type ReactNode, Suspense, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { cx } from "../../shared/ui/cx";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import styles from "./Dashboard.module.css";
import { TableScroll } from "./TableScroll";

type View = "chart" | "table";

interface ChartCardProps {
  heading: string;
  /** Va arriba del gráfico y también vale para la tabla: la leyenda, por ejemplo. */
  legend?: ReactNode;
  /** Lo que cambia qué se muestra, además del gráfico o la tabla: va junto al título. */
  controls?: ReactNode;
  chart: ReactNode;
  table: ReactNode;
}

/**
 * Una tarjeta con un gráfico y su tabla equivalente.
 *
 * El canvas no se puede recorrer con teclado ni con lector de pantalla: la
 * tabla tiene los mismos valores, a un clic, y es la forma accesible de leerlos
 * (docs/design-system.md, "Gráfico de magnitud").
 */
export function ChartCard({ heading, legend, controls, chart, table }: ChartCardProps) {
  const { t } = useTranslation();
  const headingId = useId();
  const [view, setView] = useState<View>("chart");

  return (
    <section aria-labelledby={headingId} className={cx(styles.card)}>
      <div className={cx(styles.cardHeader)}>
        <h2 id={headingId} className={cx(styles.cardTitle)}>
          {heading}
        </h2>
        <SegmentedButton
          label={`${t("dashboard.view.label")}: ${heading}`}
          options={[
            { id: "chart", label: t("dashboard.view.chart") },
            { id: "table", label: t("dashboard.view.table") },
          ]}
          value={view}
          onChange={setView}
        />
      </div>
      {controls}
      {legend}
      {view === "chart" ? (
        <div className={cx(styles.chart)}>
          {/* Chart.js llega en otro archivo: la espera ocupa el mismo alto, sin saltos. */}
          <Suspense fallback={null}>{chart}</Suspense>
        </div>
      ) : (
        <TableScroll label={`${heading}: ${t("dashboard.view.table")}`}>{table}</TableScroll>
      )}
    </section>
  );
}

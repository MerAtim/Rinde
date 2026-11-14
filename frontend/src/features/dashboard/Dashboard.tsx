import { lazy } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useMonthFormatter } from "../../i18n/format";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { TableScroll } from "../../shared/ui/TableScroll";
import { useAccounts } from "../accounts/useAccounts";
import {
  type Dashboard as DashboardData,
  type DashboardErrorCode,
  isDashboardApiError,
  type Unconverted,
} from "./api";
import { ChartCard } from "./ChartCard";
import styles from "./Dashboard.module.css";
import { DashboardFilters } from "./DashboardFilters";
import { dashboardQuery, filtersFrom, type Prices, withFilters } from "./period";
import { SpendingList } from "./SpendingList";
import { FlowTable, NetWorthTable } from "./tables";
import { useDashboard } from "./useDashboard";

// Chart.js se descarga recién cuando hay un gráfico que dibujar: el ingreso no lo paga.
const NetWorthChart = lazy(() => import("./charts/NetWorthChart"));
const FlowChart = lazy(() => import("./charts/FlowChart"));

function errorCode(error: unknown): DashboardErrorCode {
  return isDashboardApiError(error) ? error.code : "UNKNOWN_ERROR";
}

/**
 * El resumen del inicio (ADR-0018 y ADR-0020): patrimonio, ingresos y gastos
 * de cada mes y gasto por categoría, en la moneda de referencia.
 *
 * Los filtros viven solo en la URL: se pueden compartir, sobreviven a recargar
 * y el botón Atrás los deshace.
 */
export function Dashboard() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const filters = filtersFrom(params);
  const dashboard = useDashboard(dashboardQuery(filters, new Date()));
  // Las archivadas también: su historia sigue contando en el período.
  const accounts = useAccounts(true);
  const setPrices = (prices: Prices) => {
    setParams(withFilters(params, { ...filters, prices }));
  };

  if (accounts.isSuccess && accounts.data.length === 0) {
    return (
      <section className={cx(styles.empty)} aria-labelledby="dashboard-empty">
        <h1 id="dashboard-empty" className={cx(styles.emptyTitle)}>
          {t("dashboard.empty.title")}
        </h1>
        <p className={cx(styles.muted)}>{t("dashboard.empty.body")}</p>
        <LinkButton to="/accounts/new" icon="add">
          {t("dashboard.empty.action")}
        </LinkButton>
      </section>
    );
  }

  return (
    <div className={cx(styles.page)}>
      <header className={cx(styles.header)}>
        <h1 className={cx(styles.title)}>{t("dashboard.title")}</h1>
        {dashboard.data ? (
          <p className={cx(styles.muted)}>
            {t("dashboard.subtitle", {
              currency: t(`dashboard.currency.${dashboard.data.reference.currency}`),
              rate: t(`dashboard.rate.${dashboard.data.reference.rate_type}`),
            })}
          </p>
        ) : null}
      </header>
      {accounts.isSuccess ? (
        <DashboardFilters
          accounts={accounts.data}
          values={filters}
          onChange={(next) => {
            setParams(withFilters(params, next));
          }}
        />
      ) : null}
      {dashboard.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("dashboard.loading")}
        </p>
      ) : null}
      {dashboard.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t(`dashboard.errors.${errorCode(dashboard.error)}`)}</Alert>
          {/* Un enlace con pesos de hoy y otra moneda de referencia: se sale sin reintentar. */}
          {errorCode(dashboard.error) === "DASHBOARD_CONSTANT_PRICES_ARS_ONLY" ? (
            <Button
              variant="tonal"
              onPress={() => {
                setPrices("nominal");
              }}
            >
              {t("dashboard.prices.backToNominal")}
            </Button>
          ) : (
            <Button
              variant="tonal"
              onPress={() => {
                void dashboard.refetch();
              }}
            >
              {t("dashboard.retry")}
            </Button>
          )}
        </div>
      ) : null}
      {dashboard.data ? (
        <Summary
          data={dashboard.data}
          isUpdating={dashboard.isPlaceholderData}
          prices={filters.prices}
          onPricesChange={setPrices}
        />
      ) : null}
    </div>
  );
}

interface SummaryProps {
  data: DashboardData;
  isUpdating: boolean;
  prices: Prices;
  onPricesChange: (prices: Prices) => void;
}

function Summary({ data, isUpdating, prices, onPricesChange }: SummaryProps) {
  const { t } = useTranslation();
  const currency = data.reference.currency;
  const today = data.net_worth.at(-1);
  // Sin ningún IPC no hay mes base: se queda en pesos de cada mes y lo dice.
  const constant = prices === "constant" && data.constant?.base_month ? data.constant : null;
  const monthly = constant ? constant.monthly : data.monthly;

  return (
    // Mientras llega el período nuevo queda el anterior, atenuado: sin saltos.
    <div className={cx(styles.summary)} aria-busy={isUpdating} data-updating={isUpdating}>
      {isUpdating ? (
        <p role="status" className={cx("visually-hidden")}>
          {t("dashboard.updating")}
        </p>
      ) : null}
      <section className={cx(styles.hero)} aria-labelledby="net-worth-today">
        <h2 id="net-worth-today" className={cx(styles.heroLabel)}>
          {t("dashboard.netWorth.heading")} · {t("dashboard.netWorth.today")}
        </h2>
        {today?.total ? (
          <MoneyAmount amount={today.total.amount} currency={today.total.currency} size="hero" />
        ) : (
          <p className={cx(styles.muted)}>{t("dashboard.netWorth.missingToday")}</p>
        )}
      </section>
      <div className={cx(styles.grid)}>
        <ChartCard
          heading={t("dashboard.netWorth.heading")}
          chart={<NetWorthChart points={data.net_worth} currency={currency} />}
          table={<NetWorthTable points={data.net_worth} />}
        />
        <ChartCard
          heading={t("dashboard.flow.heading")}
          controls={
            // El IPC mide precios en pesos: con otra moneda de referencia no se ofrece.
            currency === "ARS" ? (
              <PricesControl
                prices={prices}
                baseMonth={constant?.base_month ?? null}
                missing={prices === "constant" && !constant}
                onChange={onPricesChange}
              />
            ) : null
          }
          legend={<FlowLegend />}
          chart={<FlowChart monthly={monthly} currency={currency} />}
          table={<FlowTable monthly={monthly} />}
        />
        <SpendingList spending={data.spending} />
        {data.unconverted.length > 0 ? <UnconvertedTable items={data.unconverted} /> : null}
      </div>
    </div>
  );
}

interface PricesControlProps {
  prices: Prices;
  baseMonth: string | null;
  /** Se pidió en pesos de hoy, pero no hay ningún IPC: se ve en pesos de cada mes. */
  missing: boolean;
  onChange: (prices: Prices) => void;
}

/**
 * Pesos de cada mes o pesos de hoy (ADR-0025). Solo cambia este bloque: el
 * patrimonio y el gasto por categoría siguen en pesos de cada mes, y la nota
 * lo dice.
 */
function PricesControl({ prices, baseMonth, missing, onChange }: PricesControlProps) {
  const { t } = useTranslation();
  const monthName = useMonthFormatter();
  let description: string | undefined;
  if (baseMonth) {
    description = t("dashboard.prices.note", { month: monthName(baseMonth, "long") });
  } else if (missing) {
    description = t("dashboard.prices.missing");
  }
  return (
    <SegmentedButton
      label={t("dashboard.prices.label")}
      {...(description ? { description } : {})}
      options={[
        { id: "nominal", label: t("dashboard.prices.nominal") },
        { id: "constant", label: t("dashboard.prices.constant") },
      ]}
      value={prices}
      onChange={onChange}
    />
  );
}

/** Dos series: la leyenda va siempre, y además dice de qué lado del cero está cada una. */
function FlowLegend() {
  const { t } = useTranslation();
  return (
    <ul className={cx(styles.legend)}>
      <li>
        <span className={cx(styles.swatch)} data-series="income" aria-hidden="true" />
        {t("dashboard.flow.income")}, {t("dashboard.flow.above")}
      </li>
      <li>
        <span className={cx(styles.swatch)} data-series="expense" aria-hidden="true" />
        {t("dashboard.flow.expense")}, {t("dashboard.flow.below")}
      </li>
    </ul>
  );
}

/**
 * Lo que no se pudo convertir: se muestra en su moneda y se explica por qué no
 * suma. Una columna por moneda: casi siempre es una sola y entra en un teléfono.
 */
function UnconvertedTable({ items }: { items: Unconverted[] }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="unconverted-heading" className={cx(styles.card)}>
      <h2 id="unconverted-heading" className={cx(styles.cardTitle)}>
        {t("dashboard.unconverted.heading")}
      </h2>
      <p className={cx(styles.muted)}>{t("dashboard.unconverted.body")}</p>
      <TableScroll label={`${t("dashboard.unconverted.heading")}: ${t("dashboard.view.table")}`}>
        <table className={cx(styles.table)}>
          <caption className={cx("visually-hidden")}>{t("dashboard.unconverted.caption")}</caption>
          <thead>
            <tr>
              <td />
              {items.map((item) => (
                <th key={item.currency} scope="col" className={cx(styles.number)}>
                  {item.currency}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["balance", "income", "expense"] as const).map((concept) => (
              <tr key={concept}>
                <th scope="row">{t(`dashboard.unconverted.${concept}`)}</th>
                {items.map((item) => (
                  <td key={item.currency} className={cx(styles.number)}>
                    <MoneyAmount amount={item[concept].amount} currency={item[concept].currency} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
    </section>
  );
}

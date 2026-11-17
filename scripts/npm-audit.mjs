// Avisos de npm audit contra una lista de excepciones con fecha de revisión.
// Uso (desde frontend/): node ../scripts/npm-audit.mjs audit-exceptions.json
//
// npm audit no permite ignorar un aviso puntual: o falla por todos o por
// ninguno. Cuando un aviso no tiene versión corregida, la CI queda en rojo sin
// ninguna acción posible. Este script acepta solo los avisos listados, cada uno
// con su motivo, y falla en tres casos:
//   * un aviso de severidad moderada o mayor que no está en la lista;
//   * una excepción cuya fecha de revisión ya pasó: hay que volver a mirarla;
//   * una excepción que ya no aparece en el audit: hay que quitarla, para que
//     la lista no crezca con excepciones muertas.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SEVERITIES = new Set(["moderate", "high", "critical"]);
const ID_PATTERN = /^GHSA(-[0-9a-z]{4}){3}$/;

function fail(lines) {
  for (const line of lines) console.error(line);
  process.exit(1);
}

function loadExceptions(path) {
  const exceptions = JSON.parse(readFileSync(path, "utf8"));
  const problems = [];
  for (const entry of exceptions) {
    if (!ID_PATTERN.test(entry.id ?? ""))
      problems.push(`Identificador inválido: ${entry.id}`);
    if (!entry.package || !entry.reason)
      problems.push(`${entry.id}: falta el paquete o el motivo.`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(entry.review_by ?? "")) {
      problems.push(
        `${entry.id}: la fecha de revisión tiene que ser AAAA-MM-DD.`,
      );
    }
  }
  if (problems.length > 0) fail(problems);
  return exceptions;
}

function runAudit() {
  // Un comando fijo, sin nada de afuera: en Windows npm solo se lanza con shell.
  const result = spawnSync("npm audit --json", {
    encoding: "utf8",
    shell: true,
    maxBuffer: 64 * 1024 * 1024,
  });
  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch {
    fail(["npm audit no devolvió JSON:", result.stderr]);
  }
  if (report.error) fail(["npm audit falló:", JSON.stringify(report.error)]);
  return report;
}

/** Los avisos propios de cada paquete; los heredados los repiten. */
function advisories(report) {
  const found = new Map();
  for (const [name, vulnerability] of Object.entries(
    report.vulnerabilities ?? {},
  )) {
    for (const via of vulnerability.via) {
      if (typeof via === "string" || !SEVERITIES.has(via.severity)) continue;
      const id = via.url.split("/").pop();
      found.set(id, {
        id,
        name,
        severity: via.severity,
        title: via.title,
        url: via.url,
      });
    }
  }
  return found;
}

const exceptions = loadExceptions(process.argv[2]);
const found = advisories(runAudit());
const today = new Date().toISOString().slice(0, 10);
const problems = [];

for (const advisory of found.values()) {
  if (!exceptions.some((entry) => entry.id === advisory.id)) {
    problems.push(
      `${advisory.severity}: ${advisory.name}, ${advisory.title} (${advisory.url})`,
    );
  }
}
for (const entry of exceptions) {
  if (!found.has(entry.id)) {
    problems.push(`${entry.id} ya no aparece en el audit: quitá la excepción.`);
  } else if (entry.review_by < today) {
    problems.push(`${entry.id} venció el ${entry.review_by}: revisala.`);
  } else {
    console.log(
      `Aceptado hasta el ${entry.review_by}: ${entry.id} en ${entry.package}.`,
    );
  }
}

if (problems.length > 0) fail(problems);
console.log("Sin vulnerabilidades sin atender.");

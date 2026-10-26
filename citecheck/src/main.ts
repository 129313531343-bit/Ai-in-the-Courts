/**
 * CiteCheck AU page: parse the text, check every citation, show the results. Everything runs
 * here; the only network requests are for the site's own index files and, unless offline
 * mode is on, the Federal Register for Commonwealth section numbers.
 */
import { textFromFile } from "./extract.ts";
import { browserLoader } from "./loader.ts";
import { Checker, DEFAULTS, type Result, type State } from "./core/match.ts";
import { COURTS, parseCitations } from "./core/parse.ts";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const LABEL: Record<State, string> = { FOUND: "Found", MISMATCH: "Name–citation mismatch", NO_RECORD: "No record", CANNOT_CHECK: "Cannot check" };
const ORDER: State[] = ["MISMATCH", "NO_RECORD", "CANNOT_CHECK", "FOUND"];
const today = () => new Date().toISOString().slice(0, 10);

const EXAMPLE = `(A made-up passage, for demonstration only.)
The appellant relied on House v The King (1936) 55 CLR 499 at 504-505 and on Project Blue Sky Inc v Australian
Broadcasting Authority (1998) 194 CLR 355. She also cited Mabo v Commonwealth (1992) 175 CLR 1,
Smith v Jones [2019] NSWSC 63 and Re Example [2019] NSWSC 2500. The claim was brought under s 18 of the
Australian Consumer Law and s 52 of the Trade Practices Act 1974 (Cth), and relied on s 999 of the
Competition and Consumer Act 2010 (Cth) and s 32 of the Charter of Human Rights and Responsibilities Act 2006 (Vic).
See also Brown v Green [2019] VSC 1.`;

function render(results: Result[]): void {
  const counts = new Map<State, number>();
  for (const r of results) counts.set(r.state, (counts.get(r.state) ?? 0) + 1);
  $("summary").innerHTML = ORDER.filter((s) => counts.get(s)).map((s) =>
    `<span class="pill s-${s}">${LABEL[s]}: ${counts.get(s)}</span>`).join("");
  if (!results.length) { $("results").innerHTML = ""; return; }
  $("results").innerHTML = `<div class="tablewrap"><table><thead><tr><th>#</th><th>Citation</th><th>Result</th><th>Why</th></tr></thead><tbody>` +
    results.map((r, i) => `<tr>
      <td class="small">${i + 1}</td>
      <td><div class="cite">${esc(r.citation.raw)}</div></td>
      <td><span class="pill s-${r.state}">${LABEL[r.state]}</span></td>
      <td>${esc(r.reason)}${r.notes.length ? `<ul class="notes">${r.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
        ${r.links.length ? `<div class="links">${r.links.map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.label)} ↗</a>`).join("")}</div>` : ""}</td>
    </tr>`).join("") + "</tbody></table></div>";
}

async function run(): Promise<void> {
  const text = $<HTMLTextAreaElement>("text").value;
  const button = $<HTMLButtonElement>("run");
  const cites = parseCitations(text);
  if (!cites.length) {
    $("status").textContent = "No case or statute citations found in this text.";
    render([]);
    return;
  }
  button.disabled = true;
  $("status").textContent = `Checking ${cites.length} citation${cites.length === 1 ? "" : "s"}…`;
  const started = performance.now();
  try {
    const checker = new Checker(browserLoader, { ...DEFAULTS, offline: $<HTMLInputElement>("offline").checked, asAt: today() });
    const results = await checker.checkAll(cites);
    render(results);
    $("status").textContent = `${cites.length} citation${cites.length === 1 ? "" : "s"} checked in ` +
      `${((performance.now() - started) / 1000).toFixed(1)} s. Anything the list does not show was not recognised as a citation.`;
  } catch (e) {
    $("status").textContent = `Something went wrong while checking: ${e instanceof Error ? e.message : e}`;
  } finally {
    button.disabled = false;
  }
}

async function coverage(): Promise<void> {
  const idx = await browserLoader.json<{ court_years: { court: string; year: number; n: number; gap: number }[] }>("a/index.json");
  if (!idx) return;
  const by = new Map<string, { n: number; from: number; to: number; gaps: number[] }>();
  for (const cy of idx.court_years) {
    const e = by.get(cy.court) ?? { n: 0, from: cy.year, to: cy.year, gaps: [] };
    e.n += cy.n; e.from = Math.min(e.from, cy.year); e.to = Math.max(e.to, cy.year);
    if (cy.year >= 2015 && cy.year <= 2024) e.gaps.push(cy.gap);
    by.set(cy.court, e);
  }
  const rows = [...by].sort((a, b) => b[1].n - a[1].n);
  $("coverage").innerHTML = `<table><thead><tr><th>Court or tribunal</th><th>Code</th><th>Years</th><th>Decisions</th><th>Missing numbers, 2015–2024</th></tr></thead><tbody>` +
    rows.map(([code, e]) => {
      const gap = e.gaps.length ? `${Math.round((100 * e.gaps.reduce((a, b) => a + b, 0)) / e.gaps.length)}%` : "–";
      return `<tr><td>${esc(COURTS.get(code)?.name ?? code)}</td><td>${esc(code)}</td><td>${e.from}–${e.to}</td><td>${e.n.toLocaleString()}</td><td>${gap}</td></tr>`;
    }).join("") + "</tbody></table>";
}

$("run").addEventListener("click", () => void run());
$("example").addEventListener("click", () => { $<HTMLTextAreaElement>("text").value = EXAMPLE; void run(); });
$<HTMLInputElement>("file").addEventListener("change", async (ev) => {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  $("status").textContent = `Reading ${file.name}…`;
  try {
    $<HTMLTextAreaElement>("text").value = await textFromFile(file);
    await run();
  } catch (e) {
    $("status").textContent = `Could not read ${file.name}: ${e instanceof Error ? e.message : e}`;
  }
});
void coverage();

/**
 * Section lists for Commonwealth Acts, from the Federal Register of Legislation API.
 *
 * What leaves the browser: the Act's register id and today's date (to find the version in
 * force), then a request for that version's EPUB. No document text, citation or party name
 * is sent. The EPUB's table of contents (OEBPS/document.ncx) lists every section, including
 * those in schedules, so a section is checked by looking for its number there.
 */
import { readZipEntry } from "./zip.ts";

export const API = "https://api.prod.legislation.gov.au/v1";

export interface SectionList {
  /** registerId of the compilation read, e.g. "C2026C00405". */
  registerId: string;
  /** Date the version came into force. */
  start: string;
  /** Section numbers in the body of the Act. */
  body: Set<string>;
  /** Section numbers in each schedule, by schedule number ("2" -> {"18", ...}). */
  schedules: Map<string, Set<string>>;
}

/** Parse the EPUB table of contents into section numbers by schedule. */
export function sectionsFromNcx(ncx: string): Omit<SectionList, "registerId" | "start"> {
  const body = new Set<string>();
  const schedules = new Map<string, Set<string>>();
  let current = body;
  for (const m of ncx.matchAll(/<text>([\s\S]*?)<\/text>/g)) {
    const label = m[1]!.replace(/\u00a0/g, " ").replace(/&amp;/g, "&").trim();
    if (/^Endnotes?\b/.test(label)) break; // endnote numbers are not sections
    const sch = /^Schedule\s+(\d+[A-Z]?)\b/.exec(label);
    if (sch) {
      const set = schedules.get(sch[1]!) ?? new Set<string>();
      schedules.set(sch[1]!, set);
      current = set;
      continue;
    }
    const sec = /^(\d+[A-Z]*)\s/.exec(label);
    if (sec) current.add(sec[1]!);
  }
  return { body, schedules };
}

/** The section number a provision refers to: "52(1)(a)" -> "52", "1041H" -> "1041H". */
export function baseSection(section: string): string {
  return /^\d+[A-Z]*/.exec(section.replace(/\s/g, ""))?.[0] ?? section;
}

const cache = new Map<string, Promise<SectionList | null>>();

/** Sections of the version in force on `asAt` (YYYY-MM-DD), or null if none is found. */
export function fetchSections(titleId: string, asAt: string, fetchFn: typeof fetch = fetch): Promise<SectionList | null> {
  const key = `${titleId}@${asAt}`;
  if (!cache.has(key)) cache.set(key, load(titleId, asAt, fetchFn));
  return cache.get(key)!;
}

async function load(titleId: string, asAt: string, fetchFn: typeof fetch): Promise<SectionList | null> {
  const v = await fetchFn(`${API}/versions/find(titleid='${encodeURIComponent(titleId)}',asat=${asAt})`);
  if (!v.ok) return null;
  const version = (await v.json()) as { registerId?: string; start?: string };
  if (!version.registerId) return null;
  const doc = await fetchFn(`${API}/documents/find(registerId='${encodeURIComponent(version.registerId)}',` +
    "type='Primary',format='Epub',uniqueTypeNumber=0,volumeNumber=0,rectificationVersionNumber=0)");
  if (!doc.ok) return null;
  const ncx = await readZipEntry(new Uint8Array(await doc.arrayBuffer()), "document.ncx");
  if (!ncx) return null;
  return { registerId: version.registerId, start: (version.start ?? "").slice(0, 10),
    ...sectionsFromNcx(new TextDecoder().decode(ncx)) };
}

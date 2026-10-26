/** A case citation found in text: a medium neutral citation (MNC) or a law report citation. */
export interface CaseCitation {
  kind: "mnc" | "report";
  /** Exact text from the input, parties through pinpoint. */
  raw: string;
  /** Offsets of raw in the input. */
  start: number;
  end: number;
  /** Party names as written, or null when the citation stands alone. */
  parties: string | null;
  year: number;
  /** MNC court code as written, e.g. "NSWSC". */
  court?: string;
  number?: number;
  /** Report series, canonical abbreviation, e.g. "Qd R". */
  series?: string;
  /** Volume number, or null for series cited by year alone ("[1932] AC 562"). */
  volume?: number | null;
  page?: number;
  bracket?: "round" | "square";
  /** Pinpoint as written, e.g. "[45]" or "12–13". */
  pinpoint: string | null;
}

export interface Provision {
  /** Schedule, e.g. "2" for the Australian Consumer Law in sch 2. */
  schedule?: string;
  /** Section as written, e.g. "18", "1041H", "52(1)(a)". */
  section: string;
}

/** A reference to an Act, with any sections cited. */
export interface StatuteCitation {
  kind: "statute";
  raw: string;
  start: number;
  end: number;
  /** Title without the year, e.g. "Competition and Consumer Act". */
  title: string;
  year: number | null;
  /** "Cth", "NSW", ... or null when the text omits it. */
  jurisdiction: string | null;
  /** Set when the text uses a recognised short name, e.g. "Australian Consumer Law". */
  alias: string | null;
  provisions: Provision[];
}

export type Citation = CaseCitation | StatuteCitation;

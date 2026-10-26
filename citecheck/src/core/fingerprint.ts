/**
 * Party-name fingerprints: the TypeScript twin of aic/fingerprint.py (see its docstring for
 * the rules and why). The public indexes hold only these, never readable names.
 * tests/fingerprint.test.ts checks this file against the vectors Python wrote.
 */

const STOP = new Set(
  `v vs versus the of and re ex parte in matter pty ltd limited inc co corp plc llc no as for by
on behalf trading ta an at to with from de du da van von der den la le`.split(/\s+/),
);

export function words(text: string): string[] {
  const t = text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/&/g, " and ");
  const out: string[] = [];
  for (const w of t.replace(/[^a-z0-9]+/g, " ").trim().split(" ")) {
    if (w.length > 1 && !/^\d+$/.test(w) && !STOP.has(w) && !out.includes(w)) out.push(w);
  }
  return out;
}

export function sides(title: string): string[][] {
  return title
    .split(/\s+v\.?\s+|\s*;\s*/i)
    .map(words)
    .filter((ws) => ws.length > 0);
}

function base64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_");
}

export async function fp(word: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(word));
  return base64url(new Uint8Array(digest).slice(0, 3));
}

/** Fingerprints of each side of a party string, e.g. "Smith v Jones" -> [[fp(smith)], [fp(jones)]]. */
export async function fingerprintSides(parties: string): Promise<string[][]> {
  return Promise.all(sides(parties).map((side) => Promise.all(side.map(fp))));
}

/** Decode an index record's compact form ("ab12 cd34|ef56") into sides of fingerprints. */
export function decodeSides(encoded: string): string[][] {
  return encoded ? encoded.split("|").map((side) => (side ? side.split(" ") : [])) : [];
}

/**
 * Delete the " 2", " 3" copies that iCloud Drive makes beside files rewritten quickly (the
 * project sits in a synced Desktop folder). A file "name N.ext" is removed only when
 * "name.ext" exists next to it, so no real file can match. Runs after every build, so the
 * copies are never deployed (DECISIONS.md D040).
 */
import { existsSync, readdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = fileURLToPath(new URL("../../site/", import.meta.url));
const COPY = /^(.+) \d+(\.[A-Za-z0-9]+)$/;
let removed = 0;
function walk(dir: string): void {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) { walk(path); continue; }
    const m = COPY.exec(name);
    if (m && existsSync(join(dir, m[1]! + m[2]!))) { rmSync(path); removed++; }
  }
}
walk(SITE);
console.log(`removed ${removed} sync copies from site/`);

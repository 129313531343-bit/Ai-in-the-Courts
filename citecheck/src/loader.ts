/** Browser loader: index files are served beside the page under data/ and fetched only when needed. */
import type { Loader } from "./core/match.ts";

const base = `${import.meta.env.BASE_URL}data/`;

async function fetchOk(path: string): Promise<Response | null> {
  const r = await fetch(base + path);
  return r.ok ? r : null;
}

export const browserLoader: Loader = {
  async json<T>(path: string): Promise<T | null> {
    const r = await fetchOk(path);
    return r ? ((await r.json()) as T) : null;
  },
  async gzJson<T>(path: string): Promise<T | null> {
    const r = await fetchOk(path);
    if (!r) return null;
    const bytes = new Uint8Array(await r.arrayBuffer());
    // Gzip starts 1f 8b. If a server already decompressed the file in transit, read it as it is.
    const gz = bytes[0] === 0x1f && bytes[1] === 0x8b;
    const text = gz
      ? await new Response(new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"))).text()
      : new TextDecoder().decode(bytes);
    return JSON.parse(text) as T;
  },
};

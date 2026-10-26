/**
 * Read one file out of a zip archive (an EPUB is a zip) with the platform's own
 * DecompressionStream, so no zip library is needed in the browser or in Node.
 */

function u16(b: Uint8Array, at: number): number {
  return b[at]! | (b[at + 1]! << 8);
}
function u32(b: Uint8Array, at: number): number {
  return (b[at]! | (b[at + 1]! << 8) | (b[at + 2]! << 16) | (b[at + 3]! << 24)) >>> 0;
}

async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** The bytes of the entry whose name ends with `suffix`, or null if there is none. */
export async function readZipEntry(zip: Uint8Array, suffix: string): Promise<Uint8Array | null> {
  // End of central directory: signature 0x06054b50, within the last 64 KB + 22 bytes.
  let eocd = -1;
  for (let i = zip.length - 22; i >= Math.max(0, zip.length - 65557); i--) {
    if (u32(zip, i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a zip file");
  const entries = u16(zip, eocd + 10);
  let p = u32(zip, eocd + 16);
  const decoder = new TextDecoder();
  for (let n = 0; n < entries; n++) {
    if (u32(zip, p) !== 0x02014b50) throw new Error("bad central directory");
    const method = u16(zip, p + 10);
    const compressed = u32(zip, p + 20);
    const nameLen = u16(zip, p + 28);
    const extraLen = u16(zip, p + 30);
    const commentLen = u16(zip, p + 32);
    const local = u32(zip, p + 42);
    const name = decoder.decode(zip.subarray(p + 46, p + 46 + nameLen));
    if (name.endsWith(suffix)) {
      const start = local + 30 + u16(zip, local + 26) + u16(zip, local + 28);
      const body = zip.subarray(start, start + compressed);
      if (method === 0) return body;
      if (method === 8) return inflateRaw(body);
      throw new Error(`unsupported zip method ${method}`);
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

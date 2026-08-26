import { save } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";

interface SaveBinaryOptions {
  defaultFileName: string;
  filterName: string;
  extensions: string[]; // e.g. ["png"]
}

/**
 * Opens Tauri's native save dialog, then writes bytes to the chosen path
 * via the fs plugin. Returns the saved path, or null if the user
 * cancelled the dialog — callers must treat that as a no-op, not an error.
 */
export async function saveBinaryFile(
  data: Uint8Array,
  { defaultFileName, filterName, extensions }: SaveBinaryOptions
): Promise<string | null> {
  const path = await save({
    defaultPath: defaultFileName,
    filters: [{ name: filterName, extensions }],
  });
  if (!path) return null;

  await writeFile(path, data);
  return path;
}

export async function blobToUint8Array(blob: Blob): Promise<Uint8Array> {
  const buf = await blob.arrayBuffer();
  return new Uint8Array(buf);
}
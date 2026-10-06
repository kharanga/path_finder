import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/** Creates a unique temp directory for one test and returns its path plus a cleanup function. */
export function makeTmpDir(prefix = "path-finder-test-") {
  const path = mkdtempSync(join(tmpdir(), prefix));
  return { path, cleanup: () => rmSync(path, { recursive: true, force: true }) };
}

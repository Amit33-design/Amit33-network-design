// Writes backend/themes_def.json from api/_themes.js (the source of truth).
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { themesAsJson } from "../../../api/_themes.js";

const out = fileURLToPath(new URL("../../backend/themes_def.json", import.meta.url));
writeFileSync(out, JSON.stringify(themesAsJson(), null, 1) + "\n");
console.log(`wrote ${out}`);

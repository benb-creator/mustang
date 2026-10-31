import { compile } from "svelte/compiler";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

/** Svelte comments out an unused selector. In a selector list,
 * that comment may not end, and swallows the following rules. */
test("Every style rule of the mobile bottom bar reaches the app", () => {
  let file = fileURLToPath(new URL("../../../frontend/AppsBar/AppBarM.svelte", import.meta.url));
  let source = readFileSync(file, "utf8");
  let result = compile(source, { filename: file, css: "external" });
  let withoutComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");
  let style = source.match(/<style>([\s\S]*)<\/style>/)[1];
  let ruleBodies = (css: string) => withoutComments(css).split("{").length - 1;
  expect(result.warnings.map(warning => warning.message)).toEqual([]);
  expect(ruleBodies(result.css.code)).toBe(ruleBodies(style));
});

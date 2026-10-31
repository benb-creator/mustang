// @vitest-environment happy-dom
import type { Message } from "../../../logic/Abstract/Message";
import DateSeparator from "../../../frontend/Chat/MessageView/DateSeparator.svelte";
import { flushSync, mount, unmount } from "svelte";
import { afterEach, expect, test } from "vitest";

let target: HTMLElement;
let app: ReturnType<typeof mount>;

afterEach(() => {
  unmount(app);
  target.remove();
});

function showSeparator(sent: Date, previousSent: Date | null): string | undefined {
  target = document.createElement("div");
  document.body.append(target);
  app = mount(DateSeparator, { target, props: {
    message: { sent } as Message,
    previousMessage: previousSent ? { sent: previousSent } as Message : null,
  } });
  flushSync();
  return target.querySelector(".date-separator")?.textContent.trim();
}

test("A message on a new day shows the day, written out", () => {
  let sent = new Date(2026, 9, 1, 10, 30);
  let separator = showSeparator(sent, new Date(2026, 8, 30, 18, 0));
  expect(separator).toContain(sent.toLocaleDateString(undefined, { weekday: "long" }));
  expect(separator).toContain(sent.toLocaleDateString(undefined, { month: "long" }));
  expect(separator).toContain("2026");
  expect(separator).toMatch(/\b1\b/);
});

test("The first message shows its day", () => {
  expect(showSeparator(new Date(2026, 9, 1, 10, 30), null)).toContain("2026");
});

test("A message on the same day as the one before shows no day", () => {
  expect(showSeparator(new Date(2026, 9, 1, 10, 30), new Date(2026, 9, 1, 8, 0))).toBeUndefined();
});

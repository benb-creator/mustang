import { afterEach, beforeEach, expect, test, vi } from "vitest";

/* logic/ shows errors by adding them to `notifications`, and must not
 * depend on Sentry. The frontend watches `notifications` and logs the
 * errors to the server. Sentry logs only in production builds. */
vi.mock("@sentry/svelte", () => ({ captureException: vi.fn() }));
vi.mock("../../../logic/build", async (importOriginal) => ({ ...await importOriginal<object>(), production: true }));

import * as Sentry from "@sentry/svelte";
import { notifications } from "../../../logic/util/Notification";
import * as logic from "../../../logic/util/error";
import { showError, showUserError, logError } from "../../../frontend/Util/error";
import { UserError } from "../../../logic/util/util";

beforeEach(() => {
  notifications.clear();
  vi.mocked(Sentry.captureException).mockClear();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("An error that logic shows is logged to the server by the frontend", () => {
  let ex = new Error("Server unreachable");

  logic.showError(ex);

  expect(notifications.contents.map(notification => notification.ex)).toEqual([ex]);
  expect(Sentry.captureException).toHaveBeenCalledWith(ex);
});

test("showError() of the frontend is the one of logic", () => {
  expect(showError).toBe(logic.showError);
});

test("The same error is shown and logged only once", () => {
  logic.showError(new Error("Server unreachable"));
  logic.showError(new Error("Server unreachable"));

  expect(notifications.length).toBe(1);
  expect(Sentry.captureException).toHaveBeenCalledTimes(1);
});

test("Background errors are neither shown nor logged in production", () => {
  logic.backgroundError(new Error("Could not parse one email"));

  expect(notifications.isEmpty).toBe(true);
  expect(Sentry.captureException).not.toHaveBeenCalled();
});

test("User errors are shown, but not logged to the server", () => {
  showUserError(new UserError("The recipient does not accept email"));

  expect(notifications.length).toBe(1);
  expect(Sentry.captureException).not.toHaveBeenCalled();
});

test("logError() logs to the server without showing the error", () => {
  let ex = new Error("Unexpected");

  logError(ex);

  expect(notifications.isEmpty).toBe(true);
  expect(Sentry.captureException).toHaveBeenCalledWith(ex);
});

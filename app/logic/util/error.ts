import { notifications, Notification, NotificationSeverity } from "./Notification";
import { production } from "../build";

export function showError(ex: Error) {
  console.error(errorMessage(ex), ex);
  if (shouldShow(ex)) {
    notifications.add(new Notification(errorMessage(ex), NotificationSeverity.Error, ex));
  }
}

export function backgroundError(ex: Error) {
  console.error(errorMessage(ex), ex);
  if (production) {
    return;
  }
  if (shouldShow(ex)) {
    notifications.add(new Notification(errorMessage(ex), NotificationSeverity.Warning, ex));
  }
}

function shouldShow(ex: Error): boolean {
  return ex?.message &&
    !(ex as any).doNotShow &&
    !notifications.find(noti => noti.message == errorMessage(ex)); // don't repeat
}

/** The account name, for errors of a specific account.
 * It's in a separate property and not in `ex.message`, because we must not
 * send it to the error log server. @see `addAccountName()` */
export function errorMessage(ex: Error): string {
  let message = ex?.message ?? ex + "";
  let accountName = (ex as any)?.accountName;
  return accountName ? `${accountName}: ${message}` : message;
}

export async function catchErrors(func: Function, errorFunc = showError) {
  try {
    await func();
  } catch (ex) {
    errorFunc(ex);
  }
}

/** In case of errors/exceptions, return a fallback value */
export function catchFallback<T>(func: () => T, fallbackResult: T): T {
  try {
    return func();
  } catch (ex) {
    return fallbackResult;
  }
}

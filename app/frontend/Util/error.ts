import * as logic from "../../logic/util/error";
import { notifications, Notification, NotificationSeverity } from "../../logic/util/Notification";
import { production } from "../../logic/build";
import * as Sentry from "@sentry/svelte";

export const showError = logic.showError;
export const backgroundError = logic.backgroundError;
export const catchErrors = logic.catchErrors;
export const catchFallback = logic.catchFallback;

export function showUserError(ex: Error, autoDisappearAfterSeconds?: number): { remove(): void } {
  let notification = new Notification(logic.errorMessage(ex), NotificationSeverity.Error, ex);
  notifications.add(notification);
  if (autoDisappearAfterSeconds) {
    setTimeout(() => {
      notifications.remove(notification);
    }, autoDisappearAfterSeconds * 1000);
  }
  return {
    remove() {
      notifications.remove(notification);
    }
  };
}

export function logError(ex: Error) {
  console.error(logic.errorMessage(ex), ex);
  logErrorToServer(ex);
}

function logErrorToServer(ex: Error) {
  try {
    if ((ex as any)?.isUserError || (ex as any)?.doNotLog) {
      return;
    }
    if (production) {
      Sentry.captureException(ex);
    }
  } catch (ex) {
    console.error(ex);
  }
}

const logNotificationErrors = {
  added(added: Notification[]) {
    for (let notification of added) {
      if (notification.ex) {
        logErrorToServer(notification.ex);
      }
    }
  },
  removed() {
  },
};
notifications.registerObserver(logNotificationErrors);
(notifications as any)._logNotificationErrors = logNotificationErrors; // HACK to keep it alive: `registerObserver()` holds it only weakly

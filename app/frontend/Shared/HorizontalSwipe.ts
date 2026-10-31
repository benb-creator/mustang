import { appGlobal } from "../../logic/app";
import { showError } from "../Util/error";
import { sleep } from "../../logic/util/util";

const kSlideMS = 180;
const kEasing = "cubic-bezier(0.2, 0.9, 0.3, 1)";

/**
 * Mobile: The content follows the finger sideways.
 * When the finger lifts after a long or fast enough swipe, the content slides out,
 * and the action for that direction runs. Otherwise, the content slides back.
 * Vertical movements are left to the browser, for scrolling.
 *
 * Usage:
 *   let swipe = new HorizontalSwipe(touchAreaE, () => [contentE]);
 *   swipe.onSwipeRight = async () => ...;
 *   ...
 *   swipe.detach();
 */
export class HorizontalSwipe {
  /** Receives the touch events */
  readonly touchAreaE: HTMLElement;
  /** The elements which follow the finger */
  readonly getContentElements: () => HTMLElement[];
  /** Finger moves to the right. null = no action in this direction */
  onSwipeRight: (() => void | Promise<void>) | null = null;
  /** Finger moves to the left. null = no action in this direction */
  onSwipeLeft: (() => void | Promise<void>) | null = null;
  /** Called while the content moves, e.g. to reveal the action underneath.
   * @param offsetX in px. Positive = to the right
   * @param armed Lifting the finger now would run the action */
  onMove: (offsetX: number, armed: boolean) => void = () => {};
  /** After the action ran, the content slides in from the other side.
   * Otherwise, it's put back in place without animation. */
  slideInAfterAction = false;
  errorCallback = showError;

  protected state: "idle" | "deciding" | "swiping" | "scrolling" = "idle";
  protected running = false;
  protected offsetX = 0;
  protected width = 0;
  protected startX = 0;
  protected startY = 0;
  protected lastX = 0;
  protected lastTime = 0;
  /** px/ms. Positive = to the right */
  protected velocityX = 0;

  constructor(touchAreaE: HTMLElement, getContentElements: () => HTMLElement[]) {
    this.touchAreaE = touchAreaE;
    this.getContentElements = getContentElements;
    touchAreaE.addEventListener("touchstart", this.touchStart, { passive: true });
    touchAreaE.addEventListener("touchmove", this.touchMove, { passive: false });
    touchAreaE.addEventListener("touchend", this.touchEnd);
    touchAreaE.addEventListener("touchcancel", this.touchCancel);
  }

  detach() {
    this.touchAreaE.removeEventListener("touchstart", this.touchStart);
    this.touchAreaE.removeEventListener("touchmove", this.touchMove);
    this.touchAreaE.removeEventListener("touchend", this.touchEnd);
    this.touchAreaE.removeEventListener("touchcancel", this.touchCancel);
  }

  /** The content slides, or the action runs */
  get isRunning(): boolean {
    return this.running;
  }

  protected touchStart = (event: TouchEvent) => {
    if (this.running || event.touches.length != 1 || this.isInHorizontalScroller(event.target as Element)) {
      this.state = "idle";
      return;
    }
    let touch = event.touches[0];
    this.startX = this.lastX = touch.clientX;
    this.startY = touch.clientY;
    this.lastTime = event.timeStamp;
    this.velocityX = 0;
    this.state = "deciding";
  }

  protected touchMove = (event: TouchEvent) => {
    if (this.state == "idle" || this.state == "scrolling" || event.defaultPrevented) {
      return;
    }
    let touch = event.touches[0];
    let deltaX = touch.clientX - this.startX;
    let deltaY = touch.clientY - this.startY;
    if (this.state == "deciding") {
      const kDecideDistance = 10;
      if (Math.abs(deltaX) < kDecideDistance && Math.abs(deltaY) < kDecideDistance) {
        return;
      }
      if (Math.abs(deltaX) < Math.abs(deltaY) * 1.5) {
        this.state = "scrolling";
        return;
      }
      this.state = "swiping";
      this.width = this.touchAreaE.offsetWidth;
    }
    event.preventDefault();
    let elapsed = event.timeStamp - this.lastTime;
    if (elapsed > 0) {
      this.velocityX = 0.7 * (touch.clientX - this.lastX) / elapsed + 0.3 * this.velocityX;
    }
    this.lastX = touch.clientX;
    this.lastTime = event.timeStamp;
    let hasAction = !!this.actionFor(deltaX);
    this.moveTo(hasAction ? deltaX : deltaX / 4, false);
    this.onMove(this.offsetX, hasAction && this.isFarEnough());
  }

  protected touchEnd = (event: TouchEvent) => {
    if (this.state != "swiping") {
      this.state = "idle";
      return;
    }
    this.state = "idle";
    event.preventDefault(); // no click after the swipe
    let action = this.actionFor(this.offsetX);
    if (!action || !this.isFarEnough()) {
      this.slideBack();
      return;
    }
    this.runAction(action)
      .catch(this.errorCallback);
  }

  protected touchCancel = () => {
    if (this.state == "swiping") {
      this.slideBack();
    }
    this.state = "idle";
  }

  /** The user wants to scroll that element sideways, e.g. a row of attachments */
  protected isInHorizontalScroller(targetE: Element): boolean {
    for (let e = targetE; e && e != this.touchAreaE; e = e.parentElement) {
      if (e.scrollWidth > e.clientWidth && /auto|scroll/.test(getComputedStyle(e).overflowX)) {
        return true;
      }
    }
    return false;
  }

  protected actionFor(offsetX: number): (() => void | Promise<void>) | null {
    return offsetX > 0 ? this.onSwipeRight : this.onSwipeLeft;
  }

  protected isFarEnough(): boolean {
    const kWidthRatio = 0.4;
    const kFlingVelocity = 0.6;
    const kFlingDistance = 48;
    let distance = Math.abs(this.offsetX);
    let isFling = Math.abs(this.velocityX) > kFlingVelocity &&
      Math.sign(this.velocityX) == Math.sign(this.offsetX) &&
      distance > kFlingDistance;
    return distance > this.width * kWidthRatio || isFling;
  }

  protected async runAction(action: () => void | Promise<void>) {
    let direction = Math.sign(this.offsetX);
    this.running = true;
    try {
      this.moveTo(direction * this.width, true);
      this.onMove(this.offsetX, true);
      await sleep(kSlideMS / 1000);
      await action();
      this.moveTo(0, false);
      this.onMove(0, false);
      if (this.slideInAfterAction) {
        this.slideIn("X", -direction);
      }
    } catch (ex) {
      this.slideBack();
      throw ex;
    } finally {
      this.running = false;
    }
  }

  /** The new content comes in from the side, e.g. the next page
   * @param axis "X" = sideways, "Y" = vertically
   * @param fromSide 1 = from the right or the bottom, -1 = from the left or the top */
  slideIn(axis: "X" | "Y", fromSide: number) {
    if (this.reducedMotion) {
      return;
    }
    for (let contentE of this.getContentElements()) {
      contentE.animate([
        { transform: `translate${axis}(${fromSide * 30}%)`, opacity: 0 },
        { transform: "none", opacity: 1 },
      ], { duration: kSlideMS, easing: kEasing });
    }
  }

  protected slideBack() {
    this.moveTo(0, true);
    this.onMove(0, false);
  }

  protected moveTo(offsetX: number, animate: boolean) {
    this.offsetX = offsetX;
    let transition = animate && !this.reducedMotion ? `transform ${kSlideMS}ms ${kEasing}` : "";
    for (let contentE of this.getContentElements()) {
      contentE.style.transition = transition;
      contentE.style.transform = offsetX ? `translateX(${offsetX}px)` : "";
    }
  }

  protected get reducedMotion(): boolean {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
}

/** Svelte action. Mobile: Swipe sideways to page, e.g. to the next day or message.
 * The page follows the finger, and the new page slides in. Does nothing on desktop.
 * Usage: `<grid use:swipePages={{ onSwipeLeft: onNext, onSwipeRight: onPrevious }}>` */
export function swipePages(pageE: HTMLElement, pages: {
  /** Finger moves to the left */
  onSwipeLeft: () => void | Promise<void>,
  /** Finger moves to the right */
  onSwipeRight: () => void | Promise<void>,
  /** Vertical paging. Vertical movements scroll, so the page doesn't follow the finger.
   * Comes from the `swipeup` and `swipedown` events of `@composi/gestures`, see `NavigationM.svelte`. */
  onSwipeUp?: () => void | Promise<void>,
  onSwipeDown?: () => void | Promise<void>,
  /** The elements which follow the finger. Default: `pageE` */
  getContentElements?: (pageE: HTMLElement) => HTMLElement[],
}) {
  if (!appGlobal.isMobile) {
    return {};
  }
  let swipe = new HorizontalSwipe(pageE, () => pages.getContentElements?.(pageE) ?? [pageE]);
  swipe.slideInAfterAction = true;
  swipe.onSwipeLeft = () => pages.onSwipeLeft();
  swipe.onSwipeRight = () => pages.onSwipeRight();
  async function onVerticalSwipe(event: Event) {
    let isUp = event.type == "swipeup";
    let action = isUp ? pages.onSwipeUp : pages.onSwipeDown;
    if (!action || swipe.isRunning) {
      return;
    }
    try {
      await action();
      swipe.slideIn("Y", isUp ? 1 : -1);
    } catch (ex) {
      swipe.errorCallback(ex);
    }
  }
  pageE.addEventListener("swipeup", onVerticalSwipe);
  pageE.addEventListener("swipedown", onVerticalSwipe);
  return {
    update(newPages: typeof pages) {
      pages = newPages;
    },
    destroy() {
      swipe.detach();
      pageE.removeEventListener("swipeup", onVerticalSwipe);
      pageE.removeEventListener("swipedown", onVerticalSwipe);
    },
  };
}

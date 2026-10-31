<hbox class="swipe-row" bind:this={rowE}>
  {#if offsetX > 0 && onSwipeRight}
    <hbox class="action right" class:armed style="--action-color: {swipeRightColor}">
      <svelte:component this={swipeRightIcon} size="24px" />
      <hbox class="label">{swipeRightLabel}</hbox>
    </hbox>
  {:else if offsetX < 0 && onSwipeLeft}
    <hbox class="action left" class:armed style="--action-color: {swipeLeftColor}">
      <hbox class="label">{swipeLeftLabel}</hbox>
      <svelte:component this={swipeLeftIcon} size="24px" />
    </hbox>
  {/if}
  <vbox flex class="content" bind:this={contentE}>
    <slot />
  </vbox>
</hbox>

<script lang="ts">
  /** Mobile: A list row which follows the finger sideways,
   * reveals the action for that direction underneath,
   * and runs it when the finger lifts after a long enough swipe. */
  import { HorizontalSwipe } from "./HorizontalSwipe";
  import { onMount } from "svelte";

  /** Finger moves to the right. null = no action */
  export let onSwipeRight: () => Promise<void> = null;
  export let swipeRightLabel: string = null;
  export let swipeRightIcon: ConstructorOfATypedSvelteComponent = null;
  export let swipeRightColor = "grey";
  /** Finger moves to the left. null = no action */
  export let onSwipeLeft: () => Promise<void> = null;
  export let swipeLeftLabel: string = null;
  export let swipeLeftIcon: ConstructorOfATypedSvelteComponent = null;
  export let swipeLeftColor = "grey";

  let rowE: HTMLElement;
  let contentE: HTMLElement;
  /** How far the row moved, in px. Positive = to the right */
  let offsetX = 0;
  /** Lifting the finger now would run the action */
  let armed = false;

  let swipe: HorizontalSwipe;
  onMount(() => {
    swipe = new HorizontalSwipe(rowE, () => [contentE]);
    swipe.onMove = (newOffsetX, newArmed) => {
      offsetX = newOffsetX;
      armed = newArmed;
    };
    return () => swipe.detach();
  });
  $: swipe && (swipe.onSwipeRight = onSwipeRight);
  $: swipe && (swipe.onSwipeLeft = onSwipeLeft);
</script>

<style>
  .swipe-row {
    position: relative;
    touch-action: pan-y;
    background-color: var(--main-bg);
  }
  :global(.mobile) .swipe-row {
    padding: 0px;
  }
  .content {
    position: relative;
    z-index: 1;
    min-width: 0;
    background-color: inherit;
  }
  .action {
    position: absolute;
    inset: 0px;
    align-items: center;
    gap: 8px;
    padding-inline: 24px;
    background-color: var(--action-color);
    color: white;
    font-weight: 500;
  }
  .action.right {
    justify-content: left;
  }
  .action.left {
    justify-content: right;
  }
  .action :global(svg) {
    transition: transform 120ms ease-out;
  }
  .action.armed :global(svg) {
    transform: scale(1.25);
  }
  .action:not(.armed) {
    opacity: 0.75;
  }
  @media (prefers-reduced-motion: reduce) {
    .action :global(svg) {
      transition: none;
    }
  }
</style>

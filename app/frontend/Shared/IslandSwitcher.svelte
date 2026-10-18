<hbox class="island specific" class:large class:border class:faint>
  <slot />
</hbox>

<script lang="ts">
  /**
   * Shows a number of buttons, which switch between multiple different views or modes.
   * Displays them as one segmented control.
   * Technically, these are radio buttons, because only 1 of them is active at any time.
   */

  export let large = false;
  export let border = true;
  /** Show the selected button not in a strong color */
  export let faint = true;
</script>

<style>
  .island {
    --island-thumb-bg: white;
    --island-hover-bg: rgba(255, 255, 255, 70%);
    gap: 2px;
  }
  @media (prefers-color-scheme: dark) {
    .island {
      --island-thumb-bg: #3A3D44;
      --island-hover-bg: rgba(255, 255, 255, 6%);
    }
  }
  .island.border {
    border: 1px solid var(--border);
    border-radius: var(--popup-radius);
    background-color: var(--offset-bg);
    padding: 2px;
  }
  .island :global(button) {
    border-radius: var(--border-radius);
    min-height: 28px;
  }
  .island :global(button.button:not(.plain)) {
    padding: 2px 8px;
  }
  .island.faint :global(button.selected:not(.hover)),
  .island.faint :global(button.selected:hover) {
    background-color: var(--island-thumb-bg);
    color: var(--fg);
    border: none;
    box-shadow: 0px 1px 2px rgba(var(--shadow-color), 16%);
  }
  .island.specific :global(button:not(.selected)) {
    background-color: transparent;
    border: none;
    color: var(--fg-muted);
  }
  .island.specific :global(button:not(.selected):hover) {
    background-color: var(--island-hover-bg);
    color: var(--fg);
  }
  .island :global(button:hover) {
    z-index: 1;
  }
  .island :global(button .label) {
    margin-inline-end: 4px;
  }
  .island :global(svg) {
    fill: transparent;
    stroke-width: 1.75px;
  }
  @media (max-width: 800px)  {
    .island.large {
      flex-direction: column;
      align-items: start;
      justify-content: stretch;
    }
  }
</style>

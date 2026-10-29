<hbox class="island specific" class:large class:border class:faint>
  <slot />
</hbox>

<script lang="ts">
  /**
   * Shows a number of buttons, which switch between multiple different views or modes.
   * Displays a rounded border around them, and each button is round as well.
   * Technically, these are radio buttons, because only 1 of them is active at any time.
   */

  export let large = false;
  export let border = true;
  /** Show the selected button not in a strong color */
  export let faint = true;
</script>

<style>
  .island.border {
    border: 1px solid var(--border);
    border-radius: var(--island-radius);
  }
  .island :global(button) {
    border-radius: var(--island-radius);
  }
  .island :global(button:not(:last-of-type)) {
    margin-inline-end: var(--island-overlap);
  }
  .island.faint :global(button.selected:not(.hover)) {
    background-color: var(--offset-bg);
    color: var(--offset-fg);
    border: none;
  }
  .island.specific :global(button:not(.selected)) {
    background-color: transparent;
    border: none;
  }
  .island :global(button:hover) {
    z-index: 1;
  }
  .island :global(button .label) {
    margin-inline-end: 4px;
  }
  .island :global(svg) {
    fill: transparent;
    stroke-width: 1.2px;
  }
  @media (max-width: 800px)  {
    .island.large {
      flex-direction: column;
      align-items: start;
      justify-content: stretch;
    }
  }
  :global(.fresh) .island {
    flex: none;
    align-items: stretch;
    box-sizing: border-box;
    height: 28px;
    max-width: 100%;
    border: 1px solid var(--border-control);
    border-radius: var(--radius-m);
    overflow: hidden;
  }
  :global(.fresh) .island:not(.border) {
    border-color: transparent;
  }
  :global(.fresh) .island.specific :global(.button.button) {
    min-width: 0;
    min-height: 0;
    margin: 0;
    padding: 0 10px;
    border: none;
    border-inline-start: 1px solid var(--border-control);
    border-radius: 0;
    background-color: transparent;
    background-image: none;
    color: var(--fg-2);
    font-weight: 500;
  }
  :global(.fresh) .island.specific :global(.button.button:first-child) {
    border-inline-start: none;
  }
  :global(.fresh) .island.specific :global(.button.button.icon-only) {
    width: 30px;
    padding: 0;
  }
  :global(.fresh) .island.specific :global(.button.button:hover:not(.disabled):not(.selected)) {
    background-color: var(--row-hover);
    color: var(--fg-1);
  }
  :global(.fresh) .island.specific :global(.button.button.selected) {
    background-color: var(--ink);
    color: var(--ink-fg);
  }
  :global(.fresh) .island.specific :global(.button.button.selected + .button) {
    border-inline-start-color: var(--ink);
  }
  :global(.fresh) .island.specific :global(.button.button.disabled:not(.selected)) {
    background-color: transparent;
    color: var(--fg-disabled);
  }
  :global(.fresh) .island.specific :global(.button.button:focus-visible) {
    outline-offset: -2px;
  }
  :global(.fresh) .island :global(.button .label) {
    margin-inline-end: 0;
  }
  :global(.fresh) .island :global(svg) {
    stroke-width: 1.75px;
  }
  </style>

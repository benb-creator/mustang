<hbox class="toolbar" class:border>
  <slot />
</hbox>

<script lang="ts">
  export let border = false;
</script>

<style>
  .toolbar {
    padding: 0px 4px;
    flex-wrap: wrap;
  }
  .toolbar.border {
    box-shadow: 1px 0px 3px 0px rgba(0, 0, 0, 30%);
    border-radius: var(--border-radius);
  }
  .toolbar :global(button.button) {
    border: none;
    border-radius: 0px;
    background-color: transparent;
    padding: 6px 6px;
    color: #595065;
  }
  .toolbar :global(button.button.disabled) {
    opacity: 20%;
  }
  :global(.fresh) .toolbar {
    align-items: center;
    gap: 4px;
    padding: 0;
  }
  :global(.fresh) .toolbar.border {
    padding: 2px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    box-shadow: none;
  }
  :global(.fresh) .toolbar :global(button.button) {
    padding: 0 8px;
    border: 1px solid transparent;
    border-radius: var(--radius-m);
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .toolbar :global(button.button.icon-only) {
    padding: 0;
    color: var(--fg-2);
  }
  :global(.fresh) .toolbar :global(button.button:hover:not(.disabled):not(.primary):not(.filled):not(.selected)) {
    border-color: transparent;
    background-color: transparent;
    background-image: linear-gradient(var(--row-hover), var(--row-hover));
    color: var(--fg-1);
  }
  :global(.fresh) .toolbar :global(button.button.selected) {
    border-color: transparent;
  }
  :global(.fresh) .toolbar :global(button.button.primary),
  :global(.fresh) .toolbar :global(button.button.filled) {
    border-color: var(--accent);
    background-color: var(--accent);
    color: var(--fg-on-accent);
  }
  :global(.fresh) .toolbar :global(button.button.disabled) {
    opacity: 1;
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-disabled);
  }
</style>

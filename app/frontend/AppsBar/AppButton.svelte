<vbox class="app-button {classes}" class:selected class:padding on:click>
  <hbox class="icon">
    <slot name="icon" />
  </hbox>
  <hbox class="label font-smallest">
    <slot name="label" />
  </hbox>
</vbox>

<script lang="ts">
  export let selected = false;
  export let classes: string = "";
  export let padding = true;
</script>

<style>
  .app-button {
    align-items: center;
    position: relative;
    margin: 2px 4px;
    border-radius: var(--popup-radius);
    color: var(--appbar-muted-fg);
    transition: background-color 80ms ease-out;
  }
  .app-button.padding {
    padding: 8px 0px 6px 0px;
  }
  .label :global(.label) {
    color: inherit;
  }
  .icon {
    opacity: 80%;
  }
  .icon :global(.cls-1) {
    stroke: var(--appbar-fg);
  }
  .app-button:hover {
    background-color: rgba(255, 255, 255, 8%);
    color: var(--appbar-fg);
  }
  .app-button:hover .icon,
  .app-button.selected .icon {
    opacity: 100%;
  }
  .app-button.selected {
    background-color: rgba(255, 255, 255, 13%);
    color: var(--appbar-fg);
  }
  .app-button.selected::before {
    content: "";
    position: absolute;
    inset-inline-start: -4px;
    top: 10px;
    bottom: 10px;
    width: 3px;
    border-start-end-radius: 2px;
    border-end-end-radius: 2px;
    background-color: var(--icon-primary);
  }
  .label {
    overflow: hidden;
    overflow-wrap: anywhere;
    text-overflow: clip;
    white-space: nowrap;
    max-width: 100%;
    margin-block-start: 3px;
    margin-inline-start: 2px;
    margin-inline-end: 2px;
    font-size: 11px;
    font-weight: 500;
  }
</style>

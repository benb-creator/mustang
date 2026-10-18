<hbox class="sub-app-button" class:selected on:click title={$title}>
  <hbox class="icon">
    <slot name="icon" />
  </hbox>
</hbox>

<script lang="ts">
  import type { MustangApp } from "./MustangApp";

  export let selected = false;
  export let app: MustangApp;

  $: title = app.title;
</script>

<style>
  .sub-app-button {
    align-items: center;
    padding: 0px;
    border-radius: var(--border-radius);
  }
  .icon {
    padding: 3px;
    color: var(--appbar-muted-fg);
  }
  .icon :global(.cls-1) {
    stroke: var(--appbar-fg);
  }
  .sub-app-button:hover {
    background-color: rgba(255, 255, 255, 8%);
  }
  .sub-app-button.selected {
    background-color: rgba(255, 255, 255, 13%);
    box-shadow: inset 0px -2px 0px 0px var(--icon-primary);
  }
  .sub-app-button.selected .icon {
    color: var(--appbar-fg);
  }

  :global(.sub-app-bar[app="webapps"]) .icon {
    filter: grayscale(0.7);
  }
</style>

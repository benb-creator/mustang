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
    border-radius: 4px;
  }
  .icon {
    padding: 2px;
  }
  .icon :global(.cls-1) {
    stroke: white;
  }
  .sub-app-button:hover {
    background-color: rgba(255, 255, 255, 25%);
  }
  .sub-app-button.selected {
    background-color: rgba(255, 255, 255, 95%);
  }
  .icon {
    color: rgba(255, 255, 255, 80%);
  }
  .sub-app-button.selected .icon {
    color: #494558 /* var(--appbar-bg) */;
  }
  .sub-app-button.selected .icon :global(.cls-1) {
    stroke: #494558 /* var(--appbar-bg) */;
  }
  .sub-app-button.selected .icon :global(.date-calendar-icon) {
    fill: #494558 /* var(--appbar-bg) */;
  }

  :global(.sub-app-bar[app="webapps"]) .icon {
    filter: grayscale(0.7);
  }
  :global(.fresh) .sub-app-button {
    flex: 0 0 auto;
    height: 36px;
    justify-content: center;
    margin-inline-start: 6px;
    border-radius: 0;
    border-start-start-radius: var(--radius-l);
    border-end-start-radius: var(--radius-l);
    cursor: pointer;
    transition: background-color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .icon {
    padding: 0;
    color: var(--spine-fg);
  }
  :global(.fresh) .icon :global(.cls-1) {
    stroke: currentColor;
  }
  :global(.fresh) .sub-app-button:hover {
    background-color: var(--spine-hover-bg);
  }
  :global(.fresh) .sub-app-button:hover .icon {
    color: var(--spine-fg-active);
  }
  :global(.fresh) .sub-app-button.selected {
    background-color: var(--l1-bg);
  }
  :global(.fresh) .sub-app-button.selected .icon {
    color: var(--accent-fg);
  }
  :global(.fresh) .sub-app-button.selected .icon :global(.cls-1) {
    stroke: currentColor;
  }
</style>

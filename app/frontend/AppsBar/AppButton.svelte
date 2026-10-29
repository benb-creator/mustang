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
  }
  .app-button.padding {
    padding: 10px 0px 6px 0px;
  }
  .label :global(.label){
    color: var(--appbar-fg);
  }
  .icon :global(.cls-1) {
    stroke: var(--appbar-fg);
  }
  .app-button:hover {
    background-color: rgba(255, 255, 255, 25%);
  }
  .app-button:hover .label {
    color: black;
  }
  .app-button.selected {
    background-color: rgba(255, 255, 255, 95%);
  }
  .app-button.selected .label :global(> .label) {
    color: black;
  }
  .icon {
    color: rgba(255, 255, 255, 80%);
  }
  .app-button.selected .icon {
    color: #494558 /* var(--appbar-bg) */;
  }
  .app-button.selected .icon :global(.cls-1) {
    stroke: #494558 /* var(--appbar-bg) */;
  }
  .app-button.selected .icon :global(.date-calendar-icon) {
    fill: #494558 /* var(--appbar-bg) */;
  }
  .label {
    color: #999999;
    overflow: hidden;
    overflow-wrap: anywhere;
    text-overflow: clip;
    white-space: nowrap;
    max-width: 100%;
    margin-block-start: 4px;
    margin-inline-start: 4px;
    margin-inline-end: 4px;
  }
  .selected .label {
    color: black;
  }
  :global(.fresh) .app-button {
    flex: 0 0 auto;
    height: 56px;
    box-sizing: border-box;
    justify-content: center;
    margin-inline-start: 6px;
    border-start-start-radius: var(--radius-l);
    border-end-start-radius: var(--radius-l);
    cursor: pointer;
    transition: background-color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .app-button.padding {
    padding: 0;
  }
  :global(.fresh) .icon,
  :global(.fresh) .label,
  :global(.fresh) .label :global(.label) {
    color: var(--spine-fg);
  }
  :global(.fresh) .icon :global(.cls-1) {
    stroke: currentColor;
  }
  :global(.fresh) .label {
    margin-block-start: var(--space-1);
    font-size: var(--text-xs);
    line-height: var(--line-xs);
    font-weight: 600;
    text-overflow: ellipsis;
  }
  :global(.fresh) .app-button:hover {
    background-color: var(--spine-hover-bg);
  }
  :global(.fresh) .app-button:hover .label,
  :global(.fresh) .app-button:hover .icon {
    color: var(--spine-fg-active);
  }
  :global(.fresh) .app-button.selected {
    background-color: var(--l1-bg);
  }
  :global(.fresh) .app-button.selected .label,
  :global(.fresh) .app-button.selected .label :global(> .label) {
    color: var(--l1-fg);
  }
  :global(.fresh) .app-button.selected .icon {
    color: var(--accent-fg);
  }
  :global(.fresh) .app-button.selected .icon :global(.cls-1) {
    stroke: currentColor;
  }
</style>

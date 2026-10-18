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
    background-color: rgba(255, 255, 255, 8%);
  }
  .app-button.selected {
    background-color: rgba(255, 255, 255, 14%);
  }
  .app-button.selected::before {
    content: "";
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    width: 3px;
    background-color: var(--icon-primary);
  }
  .icon {
    color: rgba(255, 255, 255, 80%);
  }
  .app-button:not(.selected) .label {
    opacity: 80%;
  }
  .label {
    color: var(--appbar-fg);
    overflow: hidden;
    overflow-wrap: anywhere;
    text-overflow: clip;
    white-space: nowrap;
    max-width: 100%;
    margin-block-start: 4px;
    margin-inline-start: 4px;
    margin-inline-end: 4px;
  }
</style>

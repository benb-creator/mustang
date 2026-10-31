<button class="app-button {app.id}" on:click={onClick}>
  <hbox class="icon">
    <AppIcon icon={app.icon} size="26px" />
  </hbox>
  <hbox class="name font-normal">{app.name}</hbox>
</button>

<script lang="ts">
  import { goTo } from "../selectedApp";
  import { MustangApp } from "../MustangApp";
  import AppIcon from "../AppIcon.svelte";

  export let app: MustangApp
  export let page: string;
  export let params = {};

  function onClick(event: Event) {
    event.stopPropagation();
    goTo(page, params);
  }
</script>

<style>
  .app-button {
    flex: 1 1 0;
    width: 0px;
    display: flex;
    align-items: center;
    min-height: 56px;
    padding: 6px 8px;
    border: none;
    border-radius: 16px;
    background-color: transparent;
    color: inherit;
    text-align: start;
    transition: transform 80ms ease-out, opacity 80ms ease-out;
  }
  .app-button:active {
    transform: scale(0.97);
    opacity: 0.7;
    transition: none;
  }
  .icon {
    flex: none;
    width: 44px;
    height: 44px;
    align-items: center;
    justify-content: center;
    border-radius: 14px;
    background-color: var(--appbar-bg);
    color: var(--appbar-fg);
  }
  .icon :global(.cls-1) {
    stroke: var(--appbar-fg);
  }
  .name {
    display: block;
    margin-inline-start: 14px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>

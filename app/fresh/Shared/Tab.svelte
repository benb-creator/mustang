<button class="tab" class:selected={isSelected}
  role="tab"
  aria-selected={isSelected}
  tabindex={isSelected ? 0 : -1}
  title={tooltip}
  on:click={() => select(id)}
  on:keydown={onKey}
  >
  {#if typeof(icon) == "string"}
    <Icon data={icon} size="16px" />
  {:else if icon}
    <svelte:component this={icon} size="16px" />
  {/if}
  <hbox class="label">{label}</hbox>
  {#if count}
    <Badge {count} kind="neutral" />
  {/if}
</button>

<script lang="ts">
  import Badge from "./Badge.svelte";
  import Icon from "../../frontend/Shared/Icon.svelte";
  import { getContext } from "svelte";
  import type { Writable } from "svelte/store";

  /** Identifies the tab in `<TabBar selected>` */
  export let id: string;
  export let label: string;
  export let icon: ConstructorOfATypedSvelteComponent | string = null;
  export let count: number = 0;
  export let tooltip: string = null;

  const { selectedTab, select } = getContext("tabBar") as { selectedTab: Writable<string>, select: (id: string) => void };
  $: isSelected = $selectedTab == id;

  function onKey(event: KeyboardEvent) {
    let rtl = getComputedStyle(event.currentTarget as Element).direction == "rtl";
    let next = rtl ? "ArrowLeft" : "ArrowRight";
    let previous = rtl ? "ArrowRight" : "ArrowLeft";
    let target: Element;
    if (event.key == next) {
      target = (event.currentTarget as Element).nextElementSibling;
    } else if (event.key == previous) {
      target = (event.currentTarget as Element).previousElementSibling;
    } else {
      return;
    }
    if (target instanceof HTMLElement && target.classList.contains("tab")) {
      event.preventDefault();
      target.focus();
      target.click();
    }
  }
</script>

<style>
  .tab {
    position: relative;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 12px;
    border: none;
    background-color: transparent;
    color: var(--fg-2);
    font: inherit;
    font-weight: 500;
    white-space: nowrap;
    cursor: pointer;
    transition: color var(--motion-fast) var(--motion-ease);
  }
  .tab:hover {
    color: var(--fg-1);
  }
  .tab.selected {
    color: var(--fg-1);
    font-weight: 600;
  }
  .tab.selected::after {
    content: "";
    position: absolute;
    inset-inline: 8px;
    bottom: -1px;
    height: 2px;
    background-color: var(--fg-1);
  }
  .tab:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
</style>

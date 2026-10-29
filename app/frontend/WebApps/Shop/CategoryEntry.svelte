<hbox class="category nav-entry" class:selected={category == selected}>
  {#each {length: indent} as _}
    <hbox class="indention" />
  {/each}
  <Clickable onClick={onSelect}>
    <hbox flex class="name">{category.nameTranslated}</hbox>
  </Clickable>
  {#if hasChildCategories}
    <Button plain classes="openClose" onClick={toggleOpenClose} icon={isOpen ? ChevronUpIcon : ChevronDownIcon} />
  {/if}
</hbox>
{#if isOpen}
  <Categories showCategories={childCategories} {allCategories} bind:selected indent={indent + 1} />
{/if}

<script lang="ts">
  import type { WebAppCategory } from "../../../logic/WebApps/WebAppCategory";
  import Categories from "./Categories.svelte";
  import Button from "../../Shared/Button.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import ChevronUpIcon from "lucide-svelte/icons/chevron-up";
  import ChevronDownIcon from "lucide-svelte/icons/chevron-down";
  import type { MapColl } from "svelte-collections";

  export let allCategories: MapColl<string, WebAppCategory>;
  export let category: WebAppCategory;
  export let selected: WebAppCategory; /* in/out */
  export let indent = 0;

  let childCategories = allCategories.filter(cat => cat.parentID == category.id);
  $: hasChildCategories = !$childCategories.isEmpty;

  function onSelect() {
    selected = category;
    isOpen = !isOpen;
  }

  let isOpen = false;
  function toggleOpenClose(event: Event) {
    isOpen = !isOpen;
  }
</script>

<style>
  .category {
    padding-block: 6px;
    padding-inline: 24px;
  }
  .indention {
    margin-inline-start: 24px;
  }
  .category.selected {
    background-color: var(--selected-bg);
    color: var(--selected-fg);
  }
  .category:not(.selected):hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .category.selected:hover {
    background-color: var(--selected-hover-bg);
    color: var(--selected-hover-fg);
  }
  :global(.fresh) .category {
    box-sizing: border-box;
    min-height: var(--nav-row-height);
    align-items: center;
    padding-block: 0;
    padding-inline: 16px 8px;
  }
  :global(.fresh) .category > :global(div) {
    min-width: 0;
  }
  :global(.fresh) .category .name {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  :global(.fresh) .indention {
    margin-inline-start: 16px;
  }
  :global(.fresh) .category.selected,
  :global(.fresh) .category.selected:hover {
    background-color: var(--l3-bg);
    color: var(--fg-1);
    box-shadow: inset 0 1px 0 var(--border), inset 0 -1px 0 var(--border);
  }
  :global(.fresh) .category.selected .name {
    font-weight: 600;
  }
  :global(.fresh) .category:not(.selected):hover {
    background-color: var(--row-hover);
    color: inherit;
  }
</style>

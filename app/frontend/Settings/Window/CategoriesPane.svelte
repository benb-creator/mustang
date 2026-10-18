<vbox flex class="settings-categories-pane">
  <Scroll>
    {#each $categories.each as category}
      <CategoryItem {category} />
    {/each}
  </Scroll>
</vbox>

<script lang="ts">
  import type { SettingsCategory } from "../SettingsCategory";
  import CategoryItem from "./CategoryItem.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import type { Collection } from "svelte-collections";

  /* Which apps to show on the app bar
   * in */
  export let categories: Collection<SettingsCategory>;
</script>

<style>
  .settings-categories-pane {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    border-inline-end: 1px solid var(--border);
    padding-block-start: 12px;
    z-index: 4;
  }
</style>

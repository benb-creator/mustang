<vbox flex class="settings-categories-pane">
  <Scroll hideHorizontalScrollbar>
    <vbox class="categories">
      {#each $categories.each as category}
        <CategoryItem {category} />
      {/each}
    </vbox>
  </Scroll>
</vbox>

<script lang="ts">
  import type { SettingsCategory } from "../../../frontend/Settings/SettingsCategory";
  import CategoryItem from "./CategoryItem.svelte";
  import Scroll from "../../../frontend/Shared/Scroll.svelte";
  import type { Collection } from "svelte-collections";

  /** in */
  export let categories: Collection<SettingsCategory>;
</script>

<style>
  .settings-categories-pane {
    min-width: 0;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
  }
  :global([dir="rtl"]) .settings-categories-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  .categories {
    padding-block: 12px;
  }
</style>

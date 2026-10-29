<hbox class="tab-bar" role="tablist">
  <slot />
</hbox>

<script lang="ts">
  import { setContext } from "svelte";
  import { writable } from "svelte/store";

  /** The `id` of the selected `<Tab>`
   * in/out */
  export let selected: string;

  const selectedTab = writable(selected);
  $: selectedTab.set(selected);
  function select(id: string) {
    selected = id;
  }
  setContext("tabBar", { selectedTab, select });
</script>

<style>
  .tab-bar {
    flex: none;
    align-items: stretch;
    height: 36px;
    min-width: 0;
    border-bottom: 1px solid var(--border);
  }
</style>

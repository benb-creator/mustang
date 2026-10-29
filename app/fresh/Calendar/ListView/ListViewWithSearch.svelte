<vbox class="list-view-with-search" flex>
  <ListViewWithSearch {events}>
    <PaneHeader level="l3" slot="header" let:count>
      <hbox class="range-start" slot="start">
        <slot name="top-left" />
      </hbox>
      {#if $globalSearchTerm}
        <hbox class="search">
          <SearchField bind:searchTerm={$globalSearchTerm} />
        </hbox>
        <hbox class="result-count">
          {$t`Found ${count} events`}
        </hbox>
      {/if}
      <slot name="top-right" slot="actions" />
    </PaneHeader>
  </ListViewWithSearch>
</vbox>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import ListViewWithSearch from "../../../frontend/Calendar/ListView/ListViewWithSearch.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import SearchField from "../../../frontend/Shared/SearchField.svelte";
  import { globalSearchTerm } from "../../../frontend/AppsBar/selectedApp";
  import type { Collection } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let events: Collection<Event>;
</script>

<style>
  .list-view-with-search {
    min-width: 0;
    min-height: 0;
    container: calendar-pane / inline-size;
  }
  .range-start {
    align-items: center;
    gap: 8px;
  }
  .search {
    flex: 0 1 320px;
    min-width: 120px;
  }
  .result-count {
    flex: none;
    font-size: var(--text-s);
    color: var(--fg-2);
    white-space: nowrap;
  }
</style>

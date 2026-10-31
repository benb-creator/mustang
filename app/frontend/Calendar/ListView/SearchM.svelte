<vbox class="search-page" flex>
  <ListView events={filteredEvents} />

  {#if $globalSearchTerm}
    <hbox class="result-count font-normal">
      {$t`Found ${filteredEvents.length} events`}
    </hbox>
  {/if}

  <hbox class="search-field">
    <SearchField bind:searchTerm={$globalSearchTerm} placeholder={$t`Search for an appointment`} autofocus />
  </hbox>
</vbox>
<SearchBarM />

<script lang="ts">
  import { appGlobal } from "../../../logic/app";
  import { globalSearchTerm } from "../../AppsBar/selectedApp";
  import ListView from "./ListView.svelte";
  import SearchField from "../../Shared/SearchField.svelte";
  import SearchBarM from "./SearchBarM.svelte";
  import { t } from "../../../l10n/l10n";

  export let searchTerm: string;

  $: searchTerm && setSearchTerm()
  function setSearchTerm() {
    $globalSearchTerm = searchTerm;
  }

  let events = appGlobal.calendarEvents.filterObservable(event => event.startTime.getTime() > Date.now());
  $: filteredEvents = $globalSearchTerm
    ? events.filterObservable(event => event.matchesSearch($globalSearchTerm))
    : events;
</script>

<style>
  .result-count {
    padding: 8px 16px 0px 16px;
    opacity: 75%;
  }
  .search-field {
    padding: 8px 12px;
  }
  .search-field :global(.search) {
    flex: 1 0 0;
  }
</style>

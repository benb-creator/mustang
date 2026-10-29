<vbox flex class="list-view">
  <FastList items={events}
    columns="5em var(--time-width) 1fr">
    <ListViewLine {event} slot="row" let:item={event} />
  </FastList>
</vbox>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import ListViewLine from "./ListViewLine.svelte";
  import FastList from "../../Shared/FastList.svelte";
  import type { Collection } from "svelte-collections";

  export let events: Collection<Event>;
</script>

<style>
  .list-view {
    margin-inline-start: 12px;
    max-width: 30em;
    --time-width: 3.5em;
  }
  .list-view :global(.time) {
    color: var(--fg);
  }
  .list-view :global(.title) {
    padding-inline-start: 12px;
  }
  :global(.fresh) .list-view {
    max-width: none;
    margin-inline-start: 0;
    padding-inline: 8px;
    --time-width: 6em;
  }
  :global(.fresh) .list-view :global(.time) {
    color: var(--fg-2);
  }
</style>

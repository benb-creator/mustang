<vbox class="invitation-display" class:cancelled={$event.isCancelled}>
  <hbox class="title-row">
    <hbox class="title selectable">
      {event.title ?? ""}
    </hbox>
    <hbox flex />
  </hbox>
  <vbox class="details-grid">
    <DetailsGrid {event} />
  </vbox>
</vbox>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import DetailsGrid from "../DisplayEvent/DetailsGrid.svelte";

  export let event: Event;
</script>

<style>
  .title {
    font-size: 20px;
    font-weight: bold;
  }
  .cancelled .title {
    text-decoration: line-through;
  }
  .details-grid {
    margin: 20px 16px;
  }
  :global(.fresh) .title {
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  :global(.fresh) .details-grid {
    margin: 16px 0;
  }
</style>

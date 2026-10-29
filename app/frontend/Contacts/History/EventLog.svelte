<Clickable onClick={onOpen}>
  <vbox class="event" flex>
    <div class="title">
      {event.title}
    </div>
  </vbox>
</Clickable>

<script lang="ts">
  import type { Event } from "../../../logic/Calendar/Event";
  import { openEvent } from "../../Calendar/open";
  import Clickable from "../../Shared/Clickable.svelte";

  export let event: Event;

  function onOpen() {
    openEvent(event, false);
  }
</script>

<style>
  .title {
    font-weight: bold;
  }
  :global(.fresh) .title {
    font-size: var(--text-m);
    line-height: var(--line-m);
    font-weight: 600;
    color: var(--fg-1);
  }
</style>

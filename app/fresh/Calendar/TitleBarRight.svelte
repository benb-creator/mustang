<ViewSelector bind:dateInterval />
{#if !$isCalendarListOpen}
  <SyncButton iconSize="16px" />
{/if}

<script lang="ts">
  import { isCalendarListOpen, type DateInterval } from "../../frontend/Calendar/selected";
  import ViewSelector from "./ViewSelector.svelte";
  import SyncButton from "../../frontend/Calendar/SyncButton.svelte";

  export let dateInterval: DateInterval; /* in/out */
</script>

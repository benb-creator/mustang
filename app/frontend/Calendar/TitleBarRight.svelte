<hbox class="title-bar">
  <SyncButton />
</hbox>
<ViewSelector bind:dateInterval />

<script lang="ts">
  import type { DateInterval } from "./selected";
  import ViewSelector from "./ViewSelector.svelte";
  import SyncButton from "./SyncButton.svelte";

  export let dateInterval: DateInterval; /* in/out */
</script>

<style>
  .title-bar {
    align-items: center;
    justify-content: center;
    margin: 12px;
  }
</style>

<vbox flex class="call-history">
  Call history TODO
</vbox>

{#if $appGlobal.isMobile}
  <CallHistoryBarM />
{/if}

<script lang="ts">
  import { appGlobal } from "../../../logic/app";
  import CallHistoryBarM from "./CallHistoryBarM.svelte";
</script>

<style>
  :global(.mobile) .call-history {
    align-items: center;
    justify-content: center;
    padding: 16px;
    opacity: 60%;
  }
</style>

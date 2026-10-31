<vbox flex class="pane">
  <ContactHistory {person} />
</vbox>

{#if $appGlobal.isMobile}
  <ContactHistoryBarM {person} />
{/if}

<script lang="ts">
  import { Person } from "../../logic/Abstract/Person";
  import { appGlobal } from "../../logic/app";
  import ContactHistory from "./History/ContactHistory.svelte";
  import ContactHistoryBarM from "./ContactHistoryBarM.svelte";

  export let person: Person;
</script>

<style>
  .pane :global(.group) {
    margin: 0px;
  }
  .pane :global(.group > .content) {
    border-radius: 0px;
    border-inline: none;
  }
</style>

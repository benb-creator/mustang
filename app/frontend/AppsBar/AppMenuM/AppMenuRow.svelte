<hbox class="app-row" class:selected>
  <AppButton {app} {page} {params} />
  <hbox class="actions">
    <slot />
    {#if $selectedPerson}
      <slot name="person" />
    {/if}
  </hbox>
</hbox>

<script lang="ts">
  import type { MustangApp } from "../MustangApp";
  import { selectedApp, type PageParams } from "../selectedApp";
  import { selectedPerson } from "../../Contacts/Person/Selected";
  import AppButton from "./AppButton.svelte";

  export let app: MustangApp;
  export let page: string;
  export let params: PageParams = {};

  $: selected = $selectedApp == app || app.subApps.contains($selectedApp);
</script>

<style>
  .app-row {
    container-type: inline-size;
    align-items: center;
    min-height: 56px;
    padding-inline-end: 4px;
    border-radius: 16px;
  }
  .app-row.selected {
    background-color: var(--offset-bg);
    color: var(--offset-fg);
  }
  .actions {
    align-items: center;
  }
  .actions :global(> *) {
    flex: none;
    width: 48px;
    height: 48px;
    align-items: center;
    justify-content: center;
  }
  @container (max-width: 350px) {
    .actions :global(> *) {
      width: 44px;
    }
  }
</style>

<vbox class="app-bar">
  {#each $showApps.each as app}
    <AppButton selected={selectedApp == app} classes={app.id}
      on:click={() => catchErrors(() => onSelectApp(app))} >
      <AppIcon slot="icon" icon={app.icon} size="24px" />
      <hbox slot="label" class="label">
        {app.name}
      </hbox>
    </AppButton>
    <SubAppsList mainApp={app} bind:selectedApp />
  {/each}

  <vbox flex class="middle">
    <DemoBarMiddle />
  </vbox>
  {#if $showDemoToggle}
    // #if [!WEBMAIL]
    <vbox class="above-setup">
      <DemoToggle />
    </vbox>
    // #endif
  {/if}
</vbox>

<script lang="ts">
  import type { MustangApp } from "./MustangApp";
  import { openApp, showDemoToggle } from "./selectedApp";
  import AppButton from "./AppButton.svelte";
  import AppIcon from "./AppIcon.svelte";
  import SubAppsList from "./SubAppsList.svelte";
  import DemoToggle from "./DemoToggle.svelte";
  import DemoBarMiddle from "./DemoBarMiddle.svelte";
  import { catchErrors } from "../Util/error";
  import type { Collection } from "svelte-collections";

  /* in/out */
  export let selectedApp: MustangApp;
  /* Which apps to show on the app bar
   * readonly */
  export let showApps: Collection<MustangApp>;

  function onSelectApp(app: MustangApp) {
    openApp(app, app.windowParams);
  }
</script>

<style>
  .app-bar {
    width: 64px;
    background-color: var(--appbar-bg);
    color: var(--appbar-fg);
    padding-block-start: 6px;
    z-index: 4;
  }
  .above-setup {
    position: fixed;
    width: 64px;
    bottom: 68px;
    margin: 0 auto;
  }
  .app-bar :global(.app-button.settings) {
    position: fixed;
    width: 56px;
    bottom: 8px;
  }
  .app-bar :global(.app-button.settings:not(.selected) .label .label) {
    display: none;
  }
</style>

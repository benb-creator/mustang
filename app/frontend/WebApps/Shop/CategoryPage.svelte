<vbox flex class="category-page">
  <hbox class="header">
    <h1 class="name">{category.nameTranslated}</h1>
  </hbox>
  <div class="apps">
    {#each $apps.each as app}
      <span class="app">
        <AppShopButton {app} bind:selectedApp />
      </span>
    {/each}
  </div>
</vbox>

<script lang="ts">
  import type { WebAppCategory } from "../../../logic/WebApps/WebAppCategory";
  import type { WebAppListed } from "../../../logic/WebApps/WebAppListed";
  import AppShopButton from "./WebAppShopButton.svelte";

  export let category: WebAppCategory;
  export let selectedApp: WebAppListed; /* in/out */

  $: apps = category.apps;
</script>

<style>
  .category-page {
    padding: 24px;
  }
  .header {
    margin-block-start: -32px;
  }
  h1.name {
    font-size: 24px;
  }
  div.apps {
    flex: 1 0 0;
  }
  span.app {
    display: inline-flex;
  }
  :global(.fresh) .category-page {
    padding: 0 24px 24px;
  }
  :global(.fresh) .header {
    flex: none;
    align-self: start;
    box-sizing: border-box;
    height: var(--pane-header-height);
    align-items: center;
    margin-block: calc(-1 * var(--pane-header-height)) 24px;
  }
  :global(.fresh) h1.name {
    margin: 0;
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg-1);
  }
</style>

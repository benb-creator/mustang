<vbox flex class="main-content">
  <PaneHeader level="l3" {title} large>
    <svelte:fragment slot="actions">
      <slot name="actions" />
    </svelte:fragment>
  </PaneHeader>
  <Scroll>
    <vbox flex class="settings-content">
      {#if category?.description}
        <hbox class="description">{category.description}</hbox>
      {/if}
      {#if category?.windowContent}
        <svelte:component this={category.windowContent} account={$selectedAccount} />
      {/if}
    </vbox>
  </Scroll>
</vbox>

<script lang="ts">
  import { AccountSettingsCategory, type SettingsCategory } from "../../../frontend/Settings/SettingsCategory";
  import { selectedAccount } from "../../../frontend/Settings/Window/selected";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import Scroll from "../../../frontend/Shared/Scroll.svelte";

  /** in */
  export let category: SettingsCategory;

  $: account = $selectedAccount;
  $: title = getTitle(category, $account?.name);
  function getTitle(category: SettingsCategory, accountName: string): string {
    if (category instanceof AccountSettingsCategory && accountName) {
      return accountName + " · " + category.name;
    }
    return category?.name;
  }
</script>

<style>
  .main-content {
    min-width: 0;
    min-height: 0;
  }
  .settings-content {
    box-sizing: border-box;
    max-width: 808px;
    padding: 0 24px 32px;
    font-size: var(--text-l);
    line-height: var(--line-l);
    color: var(--fg-1);
  }
  .description {
    margin-block-start: 16px;
    color: var(--fg-2);
  }
</style>

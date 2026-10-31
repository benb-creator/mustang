<vbox class="category" flex>
  <Scroll>
    <hbox class="header">
      {category?.name ?? $t`Settings`}
    </hbox>

    {#if $subCategories.hasItems}
      <vbox class="rows">
        {#each $subCategories.each as subCategory}
          <RowButton label={subCategory.name}
            icon={subCategory.icon}
            onClick={() => goToCategory(subCategory)} />
        {/each}
      </vbox>
    {/if}

    {#if category?.accounts?.hasItems}
      <hbox class="rows-header font-small">
        {$t`Accounts`}
      </hbox>
      <vbox class="rows accounts">
        {#each category.accounts.each as account}
          <RowButton label={account.name}
            icon={account.icon ?? InboxIcon}
            onClick={() => goToAccount(account)} />
        {/each}
        <RowButton label={$t`New account`} icon={PlusIcon} accent onClick={onNewAccount} />
      </vbox>
    {/if}

    {#if category?.windowContent}
      <SettingsPanelM>
        <svelte:component this={category.windowContent} account={$selectedAccount} />
      </SettingsPanelM>
    {/if}
  </Scroll>
</vbox>

{#if $appGlobal.isMobile}
  <CategoryBarM {category} />
{/if}

<script lang="ts">
  import { settingsCategories } from "../SettingsCategory";
  import type { SettingsCategory } from "../SettingsCategory";
  import { Account } from "../../../logic/Abstract/Account";
  import { selectedAccount } from "../Window/selected";
  import { SetupMustangApp } from "../../Setup/SetupMustangApp";
  import { appGlobal } from "../../../logic/app";
  import { goTo, mustangApps } from "../../AppsBar/selectedApp";
  import { URLPart } from "../../../logic/util/blob";
  import CategoryBarM from "./CategoryBarM.svelte";
  import RowButton from "./RowButton.svelte";
  import SettingsPanelM from "./SettingsPanelM.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import InboxIcon from "lucide-svelte/icons/inbox";
  import PlusIcon from "lucide-svelte/icons/plus";
  import { assert } from "../../../logic/util/util";
  import { t } from "../../../l10n/l10n";

  export let category: SettingsCategory | null;

  $: subCategories = category
    ? category.subCategories
    : settingsCategories.filterObservable(cat => cat.isMain && (!cat.forApp || mustangApps.includes(cat.forApp)));

  function goToCategory(category: SettingsCategory) {
    goTo(URLPart`/settings/category/${category.id}`, { category });
  }

  function goToAccount(account: Account) {
    goTo(URLPart`/settings/account/${account.id}`, { category, account });
  }

  function onNewAccount() {
    assert(category.newAccountURL, "Need newAccountURL");
    let setupApp = new SetupMustangApp();
    setupApp.appURL = category.newAccountURL;
    setupApp.onBack = () => onReOpenThis();
    goTo(category.newAccountURL, {});
  }

  function onReOpenThis() {
    goTo(URLPart`settings/category/${category.id}`, { category });
  }
</script>

<style>
  .category {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
  }
  .header {
    padding: 24px 16px 16px 16px;
    font-size: 28px;
    font-weight: bold;
    line-height: 1.2;
  }
  .rows {
    margin-block-end: 24px;
    border-block: 1px solid var(--border);
  }
  .rows-header {
    padding: 0 16px 8px 16px;
    font-weight: 500;
    opacity: 60%;
  }
</style>

<vbox class="category" flex>
  <Scroll>
    <hbox class="header">
      <hbox class="account-icon">
        {#if account.icon}
          <Icon data={account.icon} size="24px" />
        {:else}
          <InboxIcon size="24px" />
        {/if}
      </hbox>
      <hbox class="name">
        {account.name}
      </hbox>
    </hbox>

    {#if $subCategories.hasItems && isMain}
      <vbox class="sub-categories">
        {#each $subCategories.each as subCategory}
          <RowButton label={subCategory.name}
            icon={subCategory.icon}
            onClick={() => goToSubCategory(subCategory)} />
        {/each}
      </vbox>
    {/if}

    {#if category?.windowContent}
      <SettingsPanelM>
        <svelte:component this={category.windowContent} {account} />
      </SettingsPanelM>
    {/if}
  </Scroll>
</vbox>

{#if $appGlobal.isMobile}
  <AccountBarM {account} {category} {isMain} />
{/if}

<script lang="ts">
  import { accountSettings } from "../SettingsCategory";
  import type { SettingsCategory } from "../SettingsCategory";
  import { Account } from "../../../logic/Abstract/Account";
  import { appGlobal } from "../../../logic/app";
  import { goTo } from "../../AppsBar/selectedApp";
  import { URLPart } from "../../../logic/util/blob";
  import AccountBarM from "./AccountBarM.svelte";
  import RowButton from "./RowButton.svelte";
  import SettingsPanelM from "./SettingsPanelM.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import Icon from "../../Shared/Icon.svelte";
  import InboxIcon from "lucide-svelte/icons/inbox";

  export let account: Account;
  export let category: SettingsCategory;
  export let isMain: boolean;

  $: category = isMain ? accountSettings.find(cat => account instanceof cat.type && cat.isMain) : category;
  $: subCategories = accountSettings.filterObservable(cat => account instanceof cat.type && !cat.isMain);

  function goToSubCategory(category: SettingsCategory) {
    goTo(URLPart`/settings/account/${account.id}/${category.id}`, { account, category });
  }
</script>

<style>
  .category {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
  }
  .header {
    align-items: center;
    padding: 24px 16px 16px 16px;
    font-size: 28px;
    font-weight: bold;
    line-height: 1.2;
  }
  .account-icon {
    flex: none;
    align-items: center;
    margin-inline-end: 12px;
  }
  .name {
    min-width: 0;
  }
  .sub-categories {
    margin-block-end: 24px;
    border-block: 1px solid var(--border);
  }
</style>

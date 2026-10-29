<AccountsList {category}>
  <vbox class="header" slot="header" let:onNewAccount>
    <SectionHeader label={$t`Accounts`} level="l1">
      <svelte:fragment slot="actions">
        {#if category.newAccountURL}
          <Button
            label={$t`New account for ${category.name}`}
            icon={AddIcon}
            iconSize="14px"
            iconOnly
            plain
            classes="small"
            onClick={onNewAccount}
            />
        {/if}
      </svelte:fragment>
    </SectionHeader>
  </vbox>
  <AccountItem slot="account" let:account {account} {category} />
</AccountsList>

<script lang="ts">
  import type { SettingsCategory } from "../../../frontend/Settings/SettingsCategory";
  import AccountsList from "../../../frontend/Settings/Window/AccountsList.svelte";
  import AccountItem from "./AccountItem.svelte";
  import SectionHeader from "../../Shared/SectionHeader.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import AddIcon from "lucide-svelte/icons/plus";
  import { t } from "../../../l10n/l10n";

  /** in */
  export let category: SettingsCategory;
</script>

<style>
  .header {
    padding-block-start: 4px;
    padding-inline-start: 38px;
  }
</style>

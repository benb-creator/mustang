<MailChat {accounts}>
  <svelte:fragment slot="toolbar">
    <PaneHeader level="l1">
      <WriteButton account={$selectedAccount} />
    </PaneHeader>
    <hbox class="account">
      <AccountDropDown
        bind:selectedAccount={$selectedAccount}
        {accounts}
        filterByWorkspace={true}
        />
    </hbox>
  </svelte:fragment>
  <EmptyState slot="no-person" icon={ChatIcon} title={$t`Select a person`} />
</MailChat>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import { selectedAccount } from "../../../frontend/Mail/Selected";
  import MailChat from "../../../frontend/Mail/MailChat/MailChat.svelte";
  import WriteButton from "../LeftPane/WriteButton.svelte";
  import AccountDropDown from "../../../frontend/Shared/AccountDropDown.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import EmptyState from "../../Shared/EmptyState.svelte";
  import ChatIcon from "lucide-svelte/icons/message-square";
  import type { Collection } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let accounts: Collection<MailAccount>; /** in */
</script>

<style>
  .account {
    flex: none;
    padding: 0 12px 8px;
  }
  .account :global(.account-selector) {
    min-width: 0;
  }
</style>

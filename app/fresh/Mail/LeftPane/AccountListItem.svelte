<AccountListItem {account} let:errorMsg let:login let:openSettings let:contextMenu>
  <AccountRow {account} {expanded} {count} tooltip={errorMsg || null}
    on:click
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <hbox class="buttons" slot="actions" on:click|stopPropagation>
      {#if $account.isLoggedIn}
        <GetMailButton folder={account.inbox} />
      {:else}
        <Button
          label={$t`Login`}
          icon={DisconnectedIcon}
          onClick={login}
          iconSize="16px" plain iconOnly classes="small" />
      {/if}
      {#if account.protocol != "all"}
        <Button
          label={$t`Account settings`}
          icon={SettingsIcon}
          onClick={openSettings}
          iconSize="16px" plain iconOnly classes="small" />
      {/if}
    </hbox>
  </AccountRow>
</AccountListItem>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import AccountListItem from "../../../frontend/Mail/LeftPane/AccountListItem.svelte";
  import GetMailButton from "../../../frontend/Mail/LeftPane/GetMailButton.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import AccountRow from "../../Shared/AccountRow.svelte";
  import DisconnectedIcon from "lucide-svelte/icons/unplug";
  import SettingsIcon from "lucide-svelte/icons/settings";
  import { t } from "../../../l10n/l10n";

  export let account: MailAccount;
  export let expanded = false;

  $: inbox = account.inbox;
  $: count = expanded ? 0 : $inbox?.countNewArrived ?? 0;
</script>

<style>
  .buttons {
    align-items: center;
    gap: 2px;
  }
</style>

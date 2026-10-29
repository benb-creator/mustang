<AccountListItem {account} let:errorMsg let:login let:contextMenu>
  <AccountRow {account} {expanded}
    tooltip={errorMsg || null}
    on:click
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <hbox class="buttons" slot="actions" on:click|stopPropagation>
      {#if $account.isLoggedIn}
        <Button
          onClick={login}
          icon={SyncIcon}
          label={$t`Sync`}
          iconSize="16px" plain iconOnly classes="small"
          />
      {:else}
        <Button
          onClick={login}
          icon={DisconnectedIcon}
          label={$t`Login`}
          iconSize="16px" plain iconOnly classes="small"
          />
      {/if}
    </hbox>
  </AccountRow>
</AccountListItem>

<script lang="ts">
  import type { FileSharingAccount } from "../../../logic/Files/FileSharingAccount";
  import AccountListItem from "../../../frontend/Files/FolderLeftPane/AccountListItem.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import AccountRow from "../../Shared/AccountRow.svelte";
  import DisconnectedIcon from "lucide-svelte/icons/unplug";
  import SyncIcon from "lucide-svelte/icons/folder-sync";
  import { t } from "../../../l10n/l10n";

  export let account: FileSharingAccount;
  /** Shows the account's folders below it */
  export let expanded = false;
</script>

<style>
  .buttons {
    align-items: center;
    gap: 2px;
  }
</style>

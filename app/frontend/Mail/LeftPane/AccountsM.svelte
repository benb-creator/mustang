<vbox flex class="accounts-pane">
  {#if accounts.hasItems}
    <hbox class="accounts">
      <AccountSelectorRound {accounts} bind:selectedAccount iconDefault={AccountIcon} iconSize="24px" />
    </hbox>
  {:else if $selectedWorkspace}
    <div class="warning no-accounts font-small">
      {$t`No accounts in workspace ${$selectedWorkspace.name}`}
    </div>
  {/if}

  <FolderList {folders} bind:selectedFolder bind:selectedFolders on:click={() => catchErrors(onFolderSelected)}>
    <hbox class="folders-header font-small" slot="header">
      {selectedAccount?.name ?? $t`Folders`}
    </hbox>
  </FolderList>

  <AccountsBarM {selectedAccount} {selectedFolder} />
</vbox>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import { type Folder } from "../../../logic/Mail/Folder";
  import { selectedWorkspace } from "../../MainWindow/Selected";
  import { goTo } from "../../AppsBar/selectedApp";
  import AccountSelectorRound from "../../Shared/AccountSelectorRound.svelte";
  import FolderList from "./FolderList.svelte";
  import AccountsBarM from "./AccountsBarM.svelte";
  import AccountIcon from "lucide-svelte/icons/mail";
  import { URLPart } from "../../../logic/util/blob";
  import { catchErrors } from "../../Util/error";
  import { sleep, assert } from "../../../logic/util/util";
  import type { ArrayColl, Collection } from 'svelte-collections';
  import { t } from "../../../l10n/l10n";

  export let accounts: Collection<MailAccount>; /** in */
  export let folders: Collection<Folder>; /** in */
  export let selectedAccount: MailAccount; /** in/out */
  export let selectedFolder: Folder; /** in/out */
  let selectedFolders: ArrayColl<Folder>; /** in/out */

  async function onFolderSelected() {
    await sleep(0); // wait for `<FolderList>` to set `selectedFolder`
    assert(selectedFolder, "Need folder");
    goTo(URLPart`/mail/folder/${selectedFolder.account.id}/${selectedFolder.id ?? "noid"}/message-list`, {
      account: selectedFolder.account,
      folder: selectedFolder,
     });
  }
</script>

<style>
  .accounts-pane {
    z-index: 2;
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
  }

  .accounts {
    flex: none;
    padding-block: 12px 8px;
    border-block-end: 1px solid var(--border);
  }
  .accounts :global(.accounts) {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-inline: 8px;
    scrollbar-width: none;
  }
  .accounts :global(.account) {
    flex: none;
    width: auto;
    min-width: 64px;
    max-width: 112px;
    padding-inline: 6px;
    margin-inline-end: 0px;
  }
  .accounts :global(.account button) {
    width: 48px;
    height: 48px;
    justify-content: center;
  }
  .accounts :global(.account .name) {
    margin-block-start: 4px;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .folders-header {
    padding: 16px 16px 4px 16px !important;
    color: grey;
    font-weight: 500;
  }
  .accounts-pane :global(.folder) {
    min-height: 52px;
    padding-inline: 4px 8px;
  }
  .accounts-pane :global(.folder .label) {
    font-size: 16px;
    padding-inline-start: 16px;
  }

  .warning.no-accounts {
    text-align: center;
    color: grey;
    padding: 24px 16px;
  }
</style>

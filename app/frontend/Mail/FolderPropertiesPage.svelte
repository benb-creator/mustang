<Splitter name="mail.3pane.folders" initialRightRatio={4}>
  <vbox flex class="folder-pane" slot="left">
    <slot name="folder-pane" {folders}>
      <AccountList {accounts} bind:selectedAccount>
        <hbox class="above-accounts" slot="top-right" />
      </AccountList>
      <FolderList bind:selectedFolder={folder}  {folders} bind:selectedFolders />
    </slot>
  </vbox>
  <vbox class="main" slot="right" flex>
    <hbox class="top">
      <vbox>
        <h2>{$t`Folder`} {#if folder}- {$folder.name} - {$folder.account.name}{/if}</h2>
        <hbox class="subtitle">{$t`Rename folders, set special folders, share them with others`}</hbox>
      </vbox>
      <hbox flex />
      <hbox class="buttons">
        <RoundButton
          label={$t`Close`}
          icon={CloseIcon}
          iconSize="16px"
          onClick={onClose}
          />
        </hbox>
    </hbox>
    <vbox class="properties">
      {#if isCreating}
        <CreateFolder parentFolder={folder} location="subfolder" on:close={() => isCreating = false} />
      {:else if folder}
        <FolderProperties {folder} on:createFolder={() => isCreating = true} />
      {/if}
    </vbox>
    <hbox flex />
    <hbox class="buttons">
      <Button label={$t`Close`}
        icon={CloseIcon}
        classes="close"
        onClick={onClose}
        />
    </hbox>
  </vbox>
</Splitter>

<script lang="ts" context="module">
  export const openFolderProperties = writable<boolean>();
</script>

<script lang="ts">
  import type { Folder } from "../../logic/Mail/Folder";
  import type { MailAccount } from "../../logic/Mail/MailAccount";
  import FolderProperties from "./FolderProperties.svelte";
  import CreateFolder from "../Settings/Mail/Account/CreateFolder.svelte";
  import AccountList from "./LeftPane/AccountList.svelte";
  import FolderList from "./LeftPane/FolderList.svelte";
  import Splitter from "../Shared/Splitter.svelte";
  import Button from "../Shared/Button.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import CloseIcon from "lucide-svelte/icons/x";
  import { writable } from "svelte/store";
  import { ArrayColl, Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";

  export let folder: Folder; /** in/out */

  export let accounts: Collection<MailAccount>; /** in */
  export let selectedAccount: MailAccount; /** in/out */

  $: folders = selectedAccount ? selectedAccount.rootFolders : new ArrayColl<Folder>();

  let selectedFolders: ArrayColl<Folder>;
  let isCreating = false;

  function onClose() {
    $openFolderProperties = false;
  }
</script>

<style>
  .above-accounts {
    height: 52px;
  }
  h2 {
    margin-block-start: 0px;
    margin-block-end: 0px;
  }
  .subtitle {
    margin-block-end: 16px;
  }
  .main {
    margin: 12px 12px 12px 32px;
  }
  .properties {
    max-width: 50em;
  }
  .buttons {
    align-items: start;
    justify-content: end;
  }
  :global(.fresh) .folder-pane {
    padding-block-start: 8px;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
  }
  :global(.fresh) .above-accounts {
    height: 0;
  }
  :global(.fresh) .main {
    margin: 0;
    padding: 0;
    background-color: var(--l3-bg);
    color: var(--l3-fg);
    border-block-start: 1px solid var(--border);
  }
  :global(.fresh) .top {
    flex: none;
    box-sizing: border-box;
    min-height: var(--pane-header-height);
    align-items: start;
    gap: 8px;
    padding: 12px 24px;
    border-bottom: 1px solid var(--border-subtle);
  }
  :global(.fresh) .top h2 {
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  :global(.fresh) .subtitle {
    margin-block: 4px 0;
    color: var(--fg-2);
  }
  :global(.fresh) .top .buttons :global(.button.button.border) {
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-2);
  }
  :global(.fresh) .properties {
    padding: 16px 24px;
  }
  :global(.fresh) .main > .buttons {
    padding: 0 24px 16px;
  }
</style>

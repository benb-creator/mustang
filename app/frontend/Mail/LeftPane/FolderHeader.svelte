<!-- Appears above the msg list -->
{#if folder || searchMessages}
  <hbox class="folder-header">
    <hbox class="title">
      {#if searchMessages}
        {$t`Search results`}
      {:else if folder}
        <FolderName {folder} />
      {/if}
    </hbox>
    {#if $account?.isLoggedIn}
      <FolderMsgCount {folder} {searchMessages} />
    {/if}
    <hbox flex />
    {#if account && !$account?.isLoggedIn}
      <Button plain
        label={$t`Login`}
        icon={DisconnectedIcon}
        onClick={login}
        iconSize="16px" />
    {/if}
  </hbox>
{/if}

<script lang="ts">
  import type { Folder } from '../../../logic/Mail/Folder';
  import type { EMail } from '../../../logic/Mail/EMail';
  import FolderMsgCount from './FolderMsgCount.svelte';
  import FolderName from './FolderName.svelte';
  import Button from '../../Shared/Button.svelte';
  import DisconnectedIcon from "lucide-svelte/icons/unplug";
  import { t } from '../../../l10n/l10n';
  import type { ArrayColl } from 'svelte-collections';

  export let folder: Folder;
  export let searchMessages: ArrayColl<EMail> | null; /** in */

  $: account = folder?.account;

  async function login() {
    await account.loginAndStartup(true);
  }
</script>

<style>
  .folder-header {
    height: var(--pane-header-height);
    min-height: var(--pane-header-height);
    box-sizing: border-box;
    align-items: center;
    padding-inline: 16px 8px;
    gap: 8px;
    border-block-end: 1px solid var(--border);
  }
  .title {
    font-size: 16px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .folder-header :global(.msg-count) {
    padding-block-start: 2px;
    white-space: nowrap;
  }
  :global(.mobile) .folder-header {
    height: 40px;
    min-height: 40px;
  }
</style>

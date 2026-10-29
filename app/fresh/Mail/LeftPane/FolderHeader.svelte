<vbox class="folder-header">
  <PaneHeader title={searchMessages ? $t`Search results` : $folder?.name} {loading}>
    {#if folder}
      <FolderFooter {folder} bind:searchMessages showGetMail={false} />
    {/if}
  </PaneHeader>
  {#if account && !$account?.isLoggedIn}
    <hbox class="login">
      <LoggedOutIcon size="16px" />
      <hbox class="account-name">{$account.name}</hbox>
      <Button
        label={$t`Login`}
        icon={DisconnectedIcon}
        onClick={() => account.loginAndStartup(true)}
        iconSize="16px"
        classes="small" />
    </hbox>
  {/if}
</vbox>

<script lang="ts">
  import type { Folder } from "../../../logic/Mail/Folder";
  import type { EMail } from "../../../logic/Mail/EMail";
  import FolderFooter from "../../../frontend/Mail/LeftPane/FolderFooter.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import DisconnectedIcon from "lucide-svelte/icons/unplug";
  import LoggedOutIcon from "lucide-svelte/icons/plug-zap";
  import { t } from "../../../l10n/l10n";
  import type { ArrayColl } from "svelte-collections";

  export let folder: Folder;
  export let searchMessages: ArrayColl<EMail> | null; /** in/out */

  $: messages = folder?.messages;
  $: loading = !searchMessages && $folder?.countTotal > 0 && $messages?.isEmpty;
  $: account = folder?.account;
</script>

<style>
  .folder-header {
    flex: none;
    min-width: 0;
  }
  .folder-header :global(.pane-header .titles) {
    flex: 0 0 auto;
    max-width: 50%;
  }
  .folder-header :global(.pane-header .middle) {
    justify-content: end;
  }
  .login {
    align-items: center;
    gap: 8px;
    margin: 8px 16px 0;
    padding: 6px 8px 6px 12px;
    border: 1px solid color-mix(in srgb, var(--warning-fg) 30%, transparent);
    border-radius: var(--radius-m);
    background-color: var(--warning-tint);
    color: var(--warning-fg);
  }
  .account-name {
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--fg-1);
  }
</style>

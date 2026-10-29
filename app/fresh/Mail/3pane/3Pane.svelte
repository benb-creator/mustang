<hbox flex class="mail-layout three-pane" class:horizontal={isStacked} bind:clientWidth={width}>
  <Splitter name="mail.3pane.folders" initialRightRatio={4}>
    <LeftPane {accounts} {folders}
      bind:selectedAccount bind:selectedFolder bind:selectedFolders bind:searchMessages
      bind:activeTab={$selectedSearchTab}
      slot="left" />
    <SplitterBidirectional horizontal={isStacked}
      name={horizontal ? "mail.3pane.msgs" : "mail.widetable.msgs"}
      initialSecondRatio={horizontal ? 2 : 1}
      slot="right">
      <vbox flex class="message-list-pane" slot="first">
        <PaymentBar account={selectedAccount} showWhenNoAccount={false} />
        <FolderHeader folder={selectedFolder} bind:searchMessages />
        <TableMessageList {messages} bind:selectedMessage bind:selectedMessages />
      </vbox>
      <vbox flex class="message-display-pane" slot="second">
        {#if selectedMessage}
          <MessageDisplay message={selectedMessage} />
        {:else}
          <StartPage />
        {/if}
      </vbox>
    </SplitterBidirectional>
  </Splitter>
</hbox>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import type { Folder } from "../../../logic/Mail/Folder";
  import type { EMail } from "../../../logic/Mail/EMail";
  import { selectedSearchTab } from "../../../frontend/Mail/Selected";
  import TableMessageList from "./TableMessageList.svelte";
  import LeftPane from "../LeftPane/LeftPane.svelte";
  import FolderHeader from "../LeftPane/FolderHeader.svelte";
  import MessageDisplay from "../Message/MessageDisplay.svelte";
  import StartPage from "../StartPage.svelte";
  // #if [PROPRIETARY]
  import PaymentBar from "../../../frontend/Settings/License/Banner/PaymentBar.svelte";
  // #else
  import PaymentBar from "../../../frontend/Shared/Empty.svelte";
  // #endif
  import Splitter from "../../../frontend/Shared/Splitter.svelte";
  import SplitterBidirectional from "../../../frontend/Shared/SplitterBidirectional.svelte";
  import type { ArrayColl, Collection } from 'svelte-collections';

  export let horizontal: boolean = true;
  export let accounts: Collection<MailAccount>; /** in */
  export let messages: ArrayColl<EMail>; /** in */
  export let folders: Collection<Folder>; /** in */
  export let searchMessages: ArrayColl<EMail> | null; /** out */
  export let selectedAccount: MailAccount; /** in/out */
  export let selectedFolder: Folder; /** in/out */
  export let selectedMessage: EMail; /** in/out */
  export let selectedMessages: ArrayColl<EMail>; /** in/out */
  let selectedFolders: ArrayColl<Folder>;

  let width: number;
  $: isStacked = horizontal || width < 760;
</script>

<style>
  .mail-layout {
    background-color: var(--l2-bg);
    min-width: 0;
  }
  .message-list-pane {
    background-color: var(--l2-bg);
    color: var(--fg-1);
    border-block-start: 1px solid var(--border);
    min-width: 0;
  }
  .message-display-pane {
    flex: 2 0 0;
    background-color: var(--l3-bg);
    color: var(--l3-fg);
    border-block-start: 1px solid var(--border);
    border-inline-start: 1px solid var(--border);
    min-width: 0;
  }
  .mail-layout.horizontal .message-display-pane {
    border-inline-start: none;
  }
</style>

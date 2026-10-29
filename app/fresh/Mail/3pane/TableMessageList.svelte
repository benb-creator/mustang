<TableMessageList {messages} bind:selectedMessage bind:selectedMessages let:sortedMessages>
  <vbox flex class="message-list"
    on:keydown={event => catchErrors(() => onKeyOnList(event))}
    tabindex={0}
    >
    <FastList items={sortedMessages}
      bind:selectedItem={selectedMessage}
      bind:selectedItems={selectedMessages}
      on:init={ev => ev.detail.scrollToItem(selectedMessage)}
      columns="22px 16px minmax(0, 150px) 1fr 80px">
      <svelte:fragment slot="header">
        <hbox class="state" title={$t`Unread`}>
          <CircleIcon size="8px" />
        </hbox>
        <hbox class="attachment" title={$t`Attachments`}>
          <AttachmentIcon size="12px" />
        </hbox>
        <hbox>{$t`Correspondent`}</hbox>
        <hbox>{$t`Subject`}</hbox>
        <hbox class="date">{$t`Date`}</hbox>
      </svelte:fragment>
      <TableMessageListItem slot="row" let:item message={item} />
    </FastList>
  </vbox>
</TableMessageList>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { onKeyOnList } from "../../../frontend/Mail/Message/MessageKeyboard";
  import TableMessageList from "../../../frontend/Mail/3pane/TableMessageList.svelte";
  import FastList from "../../../frontend/Shared/FastList.svelte";
  import TableMessageListItem from "./TableMessageListItem.svelte";
  import CircleIcon from "lucide-svelte/icons/circle";
  import AttachmentIcon from "lucide-svelte/icons/paperclip";
  import type { Collection, ArrayColl } from "svelte-collections";
  import { catchErrors } from "../../../frontend/Util/error";
  import { t } from "../../../l10n/l10n";

  export let messages: Collection<EMail>;
  export let selectedMessages: ArrayColl<EMail>;
  export let selectedMessage: EMail;
</script>

<style>
  .message-list {
    min-height: 0;
  }
  .message-list:focus-visible {
    outline: none;
  }
  .message-list :global(.fast-list:focus-visible) {
    outline-offset: -2px;
  }
  .message-list :global(.fast-list .header > *) {
    position: sticky;
    top: 0;
    z-index: 1;
    box-sizing: border-box;
    height: var(--section-header-height);
    align-items: center;
    padding: 0 4px;
    border-bottom: 1px solid var(--border-subtle);
    background-color: var(--l2-bg);
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
    white-space: nowrap;
  }
  .message-list :global(.fast-list .header > :first-child) {
    padding-inline-start: 8px;
  }
  .message-list :global(.fast-list .header > :last-child) {
    padding-inline-end: 16px;
  }
  .message-list .date {
    justify-content: end;
  }
  .message-list .state,
  .message-list .attachment {
    justify-content: center;
    color: var(--fg-3);
  }
</style>

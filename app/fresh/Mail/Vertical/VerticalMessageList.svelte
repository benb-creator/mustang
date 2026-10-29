<VerticalMessageList {messages} bind:selectedMessage bind:selectedMessages bind:isAtTop let:sortedMessages>
  <vbox flex class="message-list"
    on:keydown={event => catchErrors(() => onKeyOnList(event))}
    tabindex={0}
    >
    <FastList items={sortedMessages}
      bind:selectedItem={selectedMessage}
      bind:selectedItems={selectedMessages}
      bind:isAtTop
      on:init={ev => ev.detail.scrollToItem(selectedMessage)}
      columns="auto">
      <svelte:fragment slot="header">
      </svelte:fragment>
      <VerticalMessageListItem slot="row" let:item message={item} on:click />
    </FastList>
  </vbox>
</VerticalMessageList>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { onKeyOnList } from "../../../frontend/Mail/Message/MessageKeyboard";
  import VerticalMessageList from "../../../frontend/Mail/Vertical/VerticalMessageList.svelte";
  import FastList from "../../../frontend/Shared/FastList.svelte";
  import VerticalMessageListItem from "./VerticalMessageListItem.svelte";
  import { catchErrors } from "../../../frontend/Util/error";
  import type { Collection, ArrayColl } from "svelte-collections";

  export let messages: Collection<EMail>;
  export let selectedMessage: EMail;
  export let selectedMessages: ArrayColl<EMail>;
  /** From FastList. out only */
  export let isAtTop: boolean = false;
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
  .message-list :global(.fast-list .header) {
    display: none;
  }
  .message-list :global(.fast-list .row > *) {
    padding: 0;
  }
</style>

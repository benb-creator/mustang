<vbox class="chat-rooms" flex>
  <PersonsList persons={rooms} bind:selected={selectedRoom} {doSearch}
    sortBy={room => -room.lastMessage?.sent}>
    <hbox slot="top-right" class="last-time" let:person={room}>
      {#if room instanceof ChatRoom && room.lastMessage}
        {getDateTimeString(room.lastMessage.sent)}
      {/if}
    </hbox>
    <hbox slot="second-row" flex class="last-msg font-smallest" let:person={room}>
      {#if room instanceof ChatRoom && room.lastMessage}
        {room.lastMessage.text?.substring(0, 50)}
      {/if}
    </hbox>
  </PersonsList>
</vbox>

<script lang="ts">
  import { ChatRoom } from "../../logic/Chat/ChatRoom";
  import PersonsList from "../Contacts/Person/PersonsList.svelte";
  import { getDateTimeString } from "../../logic/util/date";
  import type { Collection } from "svelte-collections";

  export let rooms: Collection<ChatRoom>;
  export let selectedRoom: ChatRoom;
  export let doSearch = false;
</script>

<style>
  .chat-rooms :global(.first-row) {
    margin-block-start: 3px;
  }
  .chat-rooms :global(.person .name) {
    font-size: medium;
  }
  .last-time {
    opacity: 50%;
    font-size: x-small;
    margin-block-start: 3px;
    margin-inline-start: 8px;
  }
  .last-msg {
    opacity: 50%;
    margin-inline-start: 1px;
    margin-block-end: 2px;
    max-height: 1.8em;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.fresh) .chat-rooms {
    min-height: 0;
  }
  :global(.fresh) .chat-rooms :global(.first-row) {
    margin: 0;
  }
  :global(.fresh) .chat-rooms :global(.person .name) {
    font-size: var(--text-m);
  }
  :global(.fresh) .last-time {
    flex: none;
    margin: 0;
    opacity: 1;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-3);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  :global(.fresh) .last-msg {
    display: block;
    min-width: 0;
    max-height: var(--line-s);
    margin: 0;
    opacity: 1;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
    white-space: nowrap;
  }
  :global(.fresh) .chat-rooms :global(.search) {
    margin-inline: 12px;
  }
  :global(.fresh) .chat-rooms :global(hbox.person) {
    padding-inline: 12px;
  }
  :global(.fresh) .chat-rooms :global(.fast-list .row.selected > *),
  :global(.fresh) .chat-rooms :global(.fast-list .row.selected:hover > *) {
    --fg-1: inherit;
    --fg-2: inherit;
    --fg-3: inherit;
    --accent-fg: inherit;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .chat-rooms :global(.fast-list .row:hover > *) {
    background-color: var(--row-hover);
  }
  :global(.fresh) .chat-rooms :global(.fast-list .person.selected.selected) {
    --fg-1: inherit;
    --fg-2: inherit;
    --fg-3: inherit;
    --accent-fg: inherit;
    box-shadow: inset 0 1px 0 var(--border), inset 0 -1px 0 var(--border);
    background-color: var(--l3-bg);
    color: var(--fg-1);
  }
</style>

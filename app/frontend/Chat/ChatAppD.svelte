<Splitter name="persons-list" initialRightRatio={4}>
  <vbox class="left-pane" slot="left">
    <slot name="header" {accounts}>
      <Header bind:selectedAccount={$selectedAccount} {accounts} />
    </slot>
    <RoomList {rooms} bind:selectedRoom={$selectedRoom} />
  </vbox>
  <vbox class="right-pane  background-pattern" slot="right">
    {#if messages && $selectedRoom }
      <PersonHeader person={$selectedRoom.contact} />
      <vbox flex class="messages">
        <MessageList {messages}>
          <svelte:fragment slot="message" let:message let:previousMessage>
            {#if message instanceof ChatMessage }
              <Message {message} {previousMessage} hideHeaderFollowup={true} />
            {:else if message instanceof ChatRoomEvent}
              <ChatRoomEventUI {message} />
            {/if}
            </svelte:fragment>
        </MessageList>
      </vbox>
      <vbox class="editor">
        <MsgEditor to={$selectedRoom} />
      </vbox>
    {/if}
  </vbox>
</Splitter>

<script lang="ts">
  import { Person } from "../../logic/Abstract/Person";
  import { ChatRoom } from "../../logic/Chat/ChatRoom";
  import { ChatPersonUID } from "../../logic/Chat/ChatPersonUID";
  import { ChatMessage } from "../../logic/Chat/ChatMessage";
  import { ChatRoomEvent } from "../../logic/Chat/RoomEvent";
  import { selectedAccount, selectedRoom } from "./selected";
  import { selectedWorkspace } from "../MainWindow/Selected";
  import { selectedPerson } from "../Contacts/Person/Selected";
  import { globalSearchTerm } from "../AppsBar/selectedApp";
  import { appGlobal } from "../../logic/app";
  import MessageList from "./MessageView/MessageList.svelte";
  import Message from "./MessageView/Message.svelte";
  import ChatRoomEventUI from "./MessageView/RoomEventUI.svelte";
  import MsgEditor from "./MsgEditor.svelte";
  import Header from "./Header.svelte";
  import PersonHeader from "./PersonHeader.svelte";
  import RoomList from "./RoomList.svelte";
  import Splitter from "../Shared/Splitter.svelte";
  import { catchErrors } from "../Util/error";
  import { mergeColls } from "svelte-collections";

  $: accounts = appGlobal.chatAccounts.filterObservable(acc => acc.workspace == $selectedWorkspace || !$selectedWorkspace);
  $: rooms = $selectedAccount ? $selectedAccount.rooms : mergeColls(accounts.map(a => a.rooms));
  $: messages = $globalSearchTerm
    ? $selectedRoom?.messages.filterObservable(msg => msg.text?.toLowerCase().includes($globalSearchTerm))
    : $selectedRoom?.messages;

  $: $selectedRoom && catchErrors(loadMessages)
  async function loadMessages() {
    await $selectedRoom?.listMembers();
    await $selectedRoom?.listMessages();
  }

  /** The person that the other apps show, e.g. the sender of the mail that the user just read.
   * Read before `linkSelectedPerson()` overwrites it with the person of the last open chat. */
  let personFromOtherApp = $selectedPerson;

  $: $rooms, selectRoom()
  /** Show the chat with the person that the other apps show. Otherwise, keep the open chat. */
  function selectRoom() {
    let personRoom = personFromOtherApp &&
      rooms.find(room => roomMatchesPerson(room, personFromOtherApp));
    if (personRoom) {
      personFromOtherApp = null; // Only when opening the app, not on every new chat
      $selectedRoom = personRoom;
    } else if (!rooms.contains($selectedRoom)) {
      $selectedRoom = rooms.last;
    }
  }
  function roomMatchesPerson(room: ChatRoom, person: Person): boolean {
    return room.contact instanceof ChatPersonUID && room.contact.matchesPerson(person);
  }

  $: linkSelectedPerson($selectedRoom);
  /** Link the open chat to an addressbook contact, so the other apps show the same person. */
  function linkSelectedPerson(room: ChatRoom | null) {
    let contact = room?.contact;
    let person = contact instanceof ChatPersonUID ? contact.findPerson()
      : contact instanceof Person ? contact : null;
    if (person) {
      $selectedPerson = person;
    }
  }
</script>

<style>
  .left-pane {
    box-shadow: var(--pane-shadow, 2px 0px 6px 0px rgba(0, 0, 0, 10%)); /* Also on MessageList */
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    margin: var(--pane-margin);
    border-radius: var(--pane-radius);
  }
  .right-pane {
    margin: var(--pane-margin);
    border-radius: var(--pane-radius);
    box-shadow: var(--pane-shadow, none);
  }
  :global(.fresh) .left-pane {
    flex: 1 1 0;
    min-width: 0;
    min-height: 0;
    margin: 0;
    border-radius: 0;
    box-shadow: inset -1px 0 0 var(--border);
    background-color: var(--l1-bg);
    color: var(--l1-fg);
  }
  :global(.fresh[dir="rtl"]) .left-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  :global(.fresh) .right-pane {
    min-width: 0;
    min-height: 0;
    margin: 0;
    border-radius: 0;
    border-block-start: 1px solid var(--border);
    box-shadow: none;
    background: var(--l3-bg);
    color: var(--l3-fg);
  }
  :global(.fresh) .messages {
    min-height: 0;
    border-block-start: 1px solid var(--border-subtle);
    background-color: var(--l2-bg);
  }
  :global(.fresh) .editor {
    flex: none;
  }
</style>

<hbox class="persons-toolbar">
  <AccountSelectorRound bind:selectedAccount {accounts} iconDefault={ChatIcon} />
  <hbox flex />
  <hbox class="buttons">
    {#if !$selectedAccount?.isLoggedIn}
      <RoundButton
        label={$t`Login`}
        icon={LoginIcon}
        classes="small"
        iconSize="12px"
        onClick={() => $selectedAccount.loginAndStartup(true)}
        />
    {/if}
    <ButtonMenu bind:isMenuOpen={isButtonMenuOpen} placement={menuPlacement}>
      <svelte:fragment slot="control">
        <slot name="new-chat" {toggleNewChatMenu}>
          <RoundButton
            label={$t`New chat`}
            icon={AddIcon}
            iconSize="22px"
            padding="9px"
            onClick={toggleNewChatMenu}
            classes="large create"
            />
        </slot>
      </svelte:fragment>
      <MenuItem
        label={$t`Chat with person`}
        onClick={() => dialogOpenPerson = true}
        />
      <MenuItem
        label={$t`Open existing chat room`}
        onClick={() => dialogOpenChatRoom = true}
        />
      <MenuItem
        label={$t`Create new chat room`}
        onClick={() => dialogNewChatRoom = true}
        />
    </ButtonMenu>
  </hbox>
</hbox>
{#if dialogOpenPerson}
  <vbox class="dialog">
    <hbox class="account">
      {$t`Chat with`}
      <AccountDropDown accounts={appGlobal.chatAccounts} bind:selectedAccount filterByWorkspace={true} />
      <RoundButton
        label={$t`Open`}
        onClick={() => dialogOpenPerson = false}
        icon={XIcon}
        iconSize="16px"
        padding="2px"
        />
    </hbox>
    <PersonAutocomplete skipPersonFunc={filterPerson} onAddPerson={openChatWithPerson} />
    <hbox class="label or">{$t`or enter chat ID`}</hbox>
    <hbox>
      <input type="text" bind:value={chatID} />
      <RoundButton
        label={$t`Open`}
        onClick={onOpenChatID}
        icon={OpenIcon}
        />
    </hbox>
  </vbox>
{:else if dialogOpenChatRoom}
  <vbox class="dialog">
    <hbox class="account">
      {$t`Open chat room`}
      <AccountDropDown accounts={appGlobal.chatAccounts} bind:selectedAccount filterByWorkspace={true} />
      <RoundButton
        label={$t`Open`}
        onClick={() => dialogOpenChatRoom = false}
        icon={XIcon}
        iconSize="16px"
        padding="2px"
        />
    </hbox>
    <input type="text" bind:value={chatID} />
    <hbox class="buttons">
      <RoundButton
        label={$t`Open`}
        onClick={onOpenChatRoom}
        icon={OpenIcon}
        />
    </hbox>
  </vbox>
{:else if dialogNewChatRoom}
{/if}


<script lang="ts">
  import type { ChatAccount } from "../../logic/Chat/ChatAccount";
  import type { PersonUID } from "../../logic/Abstract/PersonUID";
  import AccountSelectorRound from "../Shared/AccountSelectorRound.svelte";
  import PersonAutocomplete from "../Contacts/PersonAutocomplete/PersonAutocomplete.svelte";
  import ButtonMenu from "../Shared/Menu/ButtonMenu.svelte";
  import MenuItem from "../Shared/Menu/MenuItem.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import AddIcon from "lucide-svelte/icons/plus";
  import ChatIcon from "lucide-svelte/icons/message-square-text";
  import LoginIcon from "lucide-svelte/icons/key-round";
  import OpenIcon from "lucide-svelte/icons/circle-arrow-right";
  import XIcon from "lucide-svelte/icons/x";
  import { Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";
  import AccountDropDown from "../Shared/AccountDropDown.svelte";
  import { appGlobal } from "../../logic/app";
  import type { Placement } from "@popperjs/core";

  export let accounts: Collection<ChatAccount>;
  export let selectedAccount: ChatAccount;
  export let menuPlacement: Placement = "bottom-end";

  let isButtonMenuOpen = false;
  function toggleNewChatMenu() {
    isButtonMenuOpen = !isButtonMenuOpen;
  }
  let dialogOpenPerson = false;
  let dialogOpenChatRoom = false;
  let dialogNewChatRoom = false;

  function filterPerson(person: PersonUID): boolean {
    if (selectedAccount.protocol == "whatsapp") {
      return person.findPerson()?.phoneNumbers.hasItems;
    }
    return person.findPerson()?.chatAccounts.some(ce => ce.protocol == selectedAccount.protocol);
  }
  function openChatWithPerson(person: PersonUID) {
    let room = selectedAccount.newRoom(false);
    room.contact = selectedAccount.getPersonUID(person.emailAddress);
    selectedAccount.rooms.add(room);
    dialogOpenPerson = false;
  }

  let chatID: string;
  function onOpenChatID() {
    let room = selectedAccount.newRoom(false);
    room.contact = selectedAccount.getPersonUID(chatID);
    selectedAccount.rooms.add(room);
  }
  let chatRoomID: string;
  function onOpenChatRoom() {
    let room = selectedAccount.newRoom(false);
    room.contact = selectedAccount.getPersonUID(chatRoomID); // TODO which contact for group?;
    selectedAccount.rooms.add(room);
  }
</script>

<style>
  .persons-toolbar {
    margin: 10px 12px 10px 16px;
    align-items: center;
  }
  .dialog {
    margin: 32px 32px;
  }
  .dialog .account {
    margin-block-end: 12px;
    align-items: center;
  }
  .label.or {
    margin-block: 6px;
  }
  :global(.fresh) .persons-toolbar {
    flex: none;
    flex-wrap: wrap;
    gap: 0 8px;
    box-sizing: border-box;
    min-height: var(--pane-header-height);
    margin: 0;
    padding: 0 12px 8px;
  }
  :global(.fresh) .persons-toolbar > .buttons {
    display: contents;
  }
  :global(.fresh) .persons-toolbar > .buttons > :global(.menu.button) {
    order: -1;
    flex: 1 0 100%;
    box-sizing: border-box;
    height: var(--pane-header-height);
    align-items: center;
  }
  :global(.fresh) .buttons {
    align-items: center;
    gap: 4px;
  }
  :global(.fresh) .dialog {
    flex: none;
    gap: 8px;
    margin: 0 12px 12px;
    padding: 12px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-l);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
  :global(.fresh) .dialog .account {
    gap: 8px;
    margin: 0;
    font-weight: 600;
  }
  :global(.fresh) .dialog > hbox {
    align-items: center;
    gap: 8px;
  }
  :global(.fresh) .dialog input[type="text"] {
    flex: 1 1 0;
    min-width: 0;
  }
  :global(.fresh) .label.or {
    margin: 0;
    font-size: var(--text-s);
    color: var(--fg-2);
  }
  :global(.fresh) .buttons :global(.button.button) {
    min-width: var(--icon-button-size);
    min-height: var(--icon-button-size);
  }
  :global(.fresh) .persons-toolbar .buttons :global(.button.button.border:not(.filled)) {
    border-color: transparent;
    background-color: transparent;
    color: var(--fg-2);
  }
</style>

<slot name="toolbar" {sync}>
  <hbox class="persons-toolbar">
    <vbox class="dropdown">
      <AccountDropDown
        bind:selectedAccount={selectedAddressbook}
        accounts={appGlobal.addressbooks}
        showAllOption={true}
        filterByWorkspace={true}
        icon={AddressbookIcon}
        iconSize="20px"
        />
    </vbox>
    <hbox flex />
    <hbox class="buttons">
      <RoundButton
        label={$t`Sync from server`}
        icon={SyncIcon}
        iconSize="12px" padding="4px" classes="sync small" border={false}
        onClick={sync}
        disabled={!$selectedAddressbook?.canSync}
        />
      <NewContactButton {selectedAddressbook} />
    </hbox>
  </hbox>
</slot>
{#if $newPerson}
  <hbox class="new-person" class:selected={$selectedPerson == $newPerson}>
    <PersonLine person={$newPerson} {pictureSize}>
      <hbox class="new-icon" slot="icon">
        <SparklesIcon size={pictureSize} />
      </hbox>
    </PersonLine>
  </hbox>
{/if}

<script lang="ts">
  import type { Person } from "../../logic/Abstract/Person";
  import { newPerson, selectedPerson } from "./Person/Selected";
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import { appGlobal } from "../../logic/app";
  import PersonLine from "./Person/PersonLine.svelte";
  import NewContactButton from "./NewContactButton.svelte";
  import AccountDropDown from "../Shared/AccountDropDown.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import SyncIcon from "lucide-svelte/icons/refresh-cw";
  import AddressbookIcon from "lucide-svelte/icons/book-user";
  import SparklesIcon from "lucide-svelte/icons/sparkles";
  import { assert } from "../../logic/util/util";
  import type { Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";

  /** in */
  export let persons: Collection<Person>;
  /** in/out */
  export let selectedAddressbook: Addressbook;

  let pictureSize = appGlobal.isMobile ? 32 : 20;

  async function sync() {
    let ab = $selectedAddressbook;
    assert(ab?.canSync, "Cannot sync " + ab.protocol);
    if (!ab.isLoggedIn) {
      await ab.login(true);
    }
    await ab.listContacts();
  }
</script>

<style>
  .persons-toolbar {
    margin: 10px 12px 10px 16px;
    align-items: end;
  }
  .dropdown {
    margin-block: auto; /* v-center */
    margin-inline-start: 4px;
  }
  .dropdown :global(.icon) {
    margin-inline-end: 4px;
  }
  .buttons {
    align-items: end;
  }
  .buttons :global(.button) {
    margin-left: 6px;
  }
  .buttons :global(.button.disabled) {
    opacity: 10%;
  }
  .new-person {
    margin-block-end: 10px;
  }
  .new-person.selected {
    background-color: var(--selected-bg);
  }
  .new-icon {
    display: contents;
  }
  :global(.fresh) .new-person {
    flex: none;
    margin-block-end: 0;
    border-block-end: 1px solid var(--border-subtle);
  }
  :global(.fresh) .new-person.selected {
    background-color: var(--sel-inactive-bg);
  }
  :global(.fresh) .new-person > :global(.person) {
    --person-picture-size: 32px;
  }
  :global(.fresh) .new-person :global(.avatar) {
    display: none;
  }
  :global(.fresh) .new-icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: var(--signal-tint);
    color: var(--signal-strong);
  }
  :global(.fresh) .new-icon :global(svg) {
    width: 16px;
    height: 16px;
  }
</style>

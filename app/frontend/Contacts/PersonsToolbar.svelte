<vbox class="persons-toolbar">
  <hbox class="buttons">
    <Button
      label={$t`New contact`}
      icon={NewContactIcon}
      iconSize="16px"
      classes="create filled"
      onClick={addPerson}
      />
    <RoundButton
      label={$t`Sync from server`}
      icon={SyncIcon}
      iconSize="16px" padding="7px" classes="sync"
      onClick={sync}
      disabled={!$selectedAddressbook?.canSync}
      />
  </hbox>
  <hbox class="dropdown">
    <AccountDropDown
      bind:selectedAccount={selectedAddressbook}
      accounts={appGlobal.addressbooks}
      showAllOption={true}
      filterByWorkspace={true}
      icon={AddressbookIcon}
      />
  </hbox>
</vbox>
{#if $newPerson}
  <hbox class="new-person" class:selected={$selectedPerson == $newPerson}>
    <PersonLine person={$newPerson} {pictureSize}>
      <SparklesIcon size={pictureSize} slot="icon" />
    </PersonLine>
  </hbox>
{/if}

<script lang="ts">
  import type { Person } from "../../logic/Abstract/Person";
  import { newPerson, selectedPerson } from "./Person/Selected";
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import { appGlobal } from "../../logic/app";
  import PersonLine from "./Person/PersonLine.svelte";
  import AccountDropDown from "../Shared/AccountDropDown.svelte";
  import RoundButton from "../Shared/RoundButton.svelte";
  import Button from "../Shared/Button.svelte";
  import NewContactIcon from "lucide-svelte/icons/plus";
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

  function addPerson() {
    let addressbook = selectedAddressbook ?? appGlobal.addressbooks.first;
    assert(addressbook, $t`Please add an addressbook first`);
    //assert(persons instanceof ArrayColl, "Please exit the search before adding a person");
    if (!$newPerson) {
      $newPerson = addressbook.newPerson();
      $newPerson.name = "";
      $newPerson.addressbook = addressbook;
    }
    $selectedPerson = $newPerson;
  }

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
    margin-block-end: 8px;
  }
  .buttons {
    height: var(--pane-header-height);
    box-sizing: border-box;
    align-items: center;
    gap: 6px;
    padding-inline: 12px 8px;
  }
  .buttons :global(.create) {
    flex: 1 1 0;
    min-width: 0;
    justify-content: start;
    white-space: nowrap;
  }
  .buttons :global(.button.disabled) {
    opacity: 30%;
  }
  .dropdown {
    margin-inline: 12px;
  }
  .dropdown :global(.account-selector) {
    flex: 1 1 0;
    height: 32px;
    box-sizing: border-box;
    padding-inline: 8px;
    border: 1px solid var(--button-border);
    border-radius: var(--border-radius);
    background-color: var(--button-bg);
  }
  .dropdown :global(.account-selector:hover) {
    border-color: var(--border-strong);
  }
  .dropdown :global(.icon) {
    margin-block-end: 0px !important;
    margin-inline-end: 6px;
  }
  .dropdown :global(.icon svg) {
    width: 18px;
    height: 18px;
  }
  .dropdown :global(select) {
    flex: 1 1 0;
    max-width: none;
    height: 100%;
    font-size: 14px;
    font-weight: 500;
  }
  .new-person {
    margin-block-end: 10px;
  }
  .new-person.selected {
    background-color: var(--selected-bg);
  }
</style>

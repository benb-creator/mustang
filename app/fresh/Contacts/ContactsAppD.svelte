<hbox flex class="contacts-app">
  <vbox class="addressbooks-pane">
    <PaneHeader level="l1">
      <NewContactButton {selectedAddressbook} />
    </PaneHeader>
    <SectionHeader label={$t`Address books`} level="l1" />
    <AddressbookSelector bind:selectedAddressbook />
  </vbox>
  <ContactsAppD bind:selectedAddressbook initialRightRatio={3} leftMinWidth={220} rightMinWidth={320}>
    <vbox flex class="persons-pane" class:show-addressbook={!selectedAddressbook && $addressbooks.length > 1} slot="persons" let:persons>
      <PersonsToolbar {persons} bind:selectedAddressbook />
      <PersonsActionToolbar bind:selectedAddressbook {selectedPersons} />
      <PersonsList {persons} bind:selected={$selectedPerson} searchTerm={$globalSearchTerm} bind:selectedPersons>
        <hbox class="person-info" slot="second-row" let:person>{personInfo(person)}</hbox>
        <EmptyState slot="no-results" icon={NoResultsIcon} title={$t`No matches`} />
      </PersonsList>
    </vbox>
    <vbox flex class="person-pane" slot="person">
      {#if $selectedPerson && $selectedPerson instanceof Person}
        <PersonDetails person={$selectedPerson} />
      {:else}
        <EmptyState icon={PersonIcon} title={$t`Select a person`}>
          <NewContactButton {selectedAddressbook} slot="action" />
        </EmptyState>
      {/if}
    </vbox>
  </ContactsAppD>
</hbox>

<script lang="ts">
  import { Person } from "../../logic/Abstract/Person";
  import type { PersonOrGroup } from "../../frontend/Contacts/Person/PersonOrGroup";
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import { selectedPerson } from "../../frontend/Contacts/Person/Selected";
  import { globalSearchTerm } from "../../frontend/AppsBar/selectedApp";
  import { appGlobal } from "../../logic/app";
  import ContactsAppD from "../../frontend/Contacts/ContactsAppD.svelte";
  import AddressbookSelector from "./AddressbookSelector.svelte";
  import PersonsToolbar from "./PersonsToolbar.svelte";
  import NewContactButton from "./NewContactButton.svelte";
  import PersonDetails from "./PersonPage/PersonDetails.svelte";
  import PersonsActionToolbar from "../../frontend/Contacts/PersonsActionToolbar.svelte";
  import PersonsList from "../../frontend/Contacts/Person/PersonsList.svelte";
  import PaneHeader from "../Shared/PaneHeader.svelte";
  import SectionHeader from "../Shared/SectionHeader.svelte";
  import EmptyState from "../Shared/EmptyState.svelte";
  import PersonIcon from "lucide-svelte/icons/contact-round";
  import NoResultsIcon from "lucide-svelte/icons/search-x";
  import type { ArrayColl } from "svelte-collections";
  import { t } from "../../l10n/l10n";

  let selectedAddressbook: Addressbook | null = null;
  let selectedPersons: ArrayColl<PersonOrGroup>;
  let addressbooks = appGlobal.addressbooks;

  function personInfo(person: unknown): string {
    if (!(person instanceof Person)) {
      return "";
    }
    let job = [person.position, person.company].filter(part => part).join(" · ");
    return job || person.emailAddresses.first?.value || "";
  }
</script>

<style>
  .contacts-app {
    min-width: 0;
    min-height: 0;
  }
  .addressbooks-pane {
    width: 20cqi;
    min-width: 160px;
    container-type: inline-size;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
  }
  :global([dir="rtl"]) .addressbooks-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  .persons-pane {
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    background-color: var(--l2-bg);
    color: var(--fg-1);
  }
  .person-pane {
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    border-inline-start: 1px solid var(--border);
    background-color: var(--l3-bg);
    color: var(--l3-fg);
  }
  .person-info {
    display: block;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
</style>

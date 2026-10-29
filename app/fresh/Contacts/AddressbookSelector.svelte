<vbox flex class="addressbooks">
  <NavRow
    label={$t`All address books`}
    icon={AllIcon}
    selected={!selectedAddressbook}
    on:click={() => onSelect(null)}
    />
  {#each $addressbooks.each as addressbook (addressbook.id)}
    <NavRow
      label={addressbook.name}
      selected={addressbook == selectedAddressbook}
      on:click={() => onSelect(addressbook)}
      >
      <svelte:fragment slot="icon">
        {#if typeof(addressbook.icon) == "string"}
          <img src={addressbook.icon} width="16" height="16" alt="" />
        {:else}
          <svelte:component this={addressbook.icon ?? (addressbook == appGlobal.collectedAddressbook ? CollectedIcon : AddressbookIcon)} size="16px" />
        {/if}
      </svelte:fragment>
    </NavRow>
  {/each}
</vbox>

<script lang="ts">
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import type { Workspace } from "../../logic/Abstract/Workspace";
  import { selectedWorkspace } from "../../frontend/MainWindow/Selected";
  import { appGlobal } from "../../logic/app";
  import NavRow from "../Shared/NavRow.svelte";
  import AddressbookIcon from "lucide-svelte/icons/book-user";
  import AllIcon from "lucide-svelte/icons/library-big";
  import CollectedIcon from "lucide-svelte/icons/history";
  import type { Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";
  import { createEventDispatcher } from "svelte";
  const dispatch = createEventDispatcher<{ select: Addressbook }>();

  /** null = all address books
   * in/out */
  export let selectedAddressbook: Addressbook | null;

  $: addressbooks = workspaceAddressbooks($selectedWorkspace);
  function workspaceAddressbooks(workspace: Workspace | null): Collection<Addressbook> {
    if (workspace) {
      return appGlobal.addressbooks.filterObservable(ab => ab.workspace == workspace);
    }
    return appGlobal.addressbooks;
  }

  $: $addressbooks, onAddressbooksChanged();
  function onAddressbooksChanged() {
    if (selectedAddressbook && !addressbooks.contains(selectedAddressbook)) {
      onSelect(null);
    }
  }

  function onSelect(addressbook: Addressbook | null) {
    selectedAddressbook = addressbook;
    dispatch("select", addressbook);
  }
</script>

<style>
  .addressbooks {
    overflow-y: auto;
    padding-block-end: 8px;
  }
  .addressbooks img {
    border-radius: var(--radius-s);
  }
</style>

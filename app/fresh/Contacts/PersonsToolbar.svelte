<PersonsToolbar {persons} bind:selectedAddressbook>
  <svelte:fragment slot="toolbar" let:sync>
    <PaneHeader title={selectedAddressbook?.name ?? $t`All address books`} subtitle={$persons.length ? String($persons.length) : null}>
      <Button
        label={$t`Sync from server`}
        icon={SyncIcon}
        iconOnly plain
        onClick={sync}
        disabled={!$selectedAddressbook?.canSync}
        slot="actions"
        />
    </PaneHeader>
  </svelte:fragment>
</PersonsToolbar>

<script lang="ts">
  import type { Person } from "../../logic/Abstract/Person";
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import PersonsToolbar from "../../frontend/Contacts/PersonsToolbar.svelte";
  import PaneHeader from "../Shared/PaneHeader.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import SyncIcon from "lucide-svelte/icons/refresh-cw";
  import type { Collection } from "svelte-collections";
  import { t } from "../../l10n/l10n";

  /** in */
  export let persons: Collection<Person>;
  /** null = all address books
   * in/out */
  export let selectedAddressbook: Addressbook | null;
</script>

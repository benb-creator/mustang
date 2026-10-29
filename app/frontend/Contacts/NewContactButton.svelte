<slot {addPerson}>
  <RoundButton
    label={$t`New contact`}
    icon={NewContactIcon}
    iconSize="22px" padding="9px" classes="large create"
    onClick={addPerson}
    />
</slot>

<script lang="ts">
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import { newPerson, selectedPerson } from "./Person/Selected";
  import { appGlobal } from "../../logic/app";
  import RoundButton from "../Shared/RoundButton.svelte";
  import NewContactIcon from "lucide-svelte/icons/plus";
  import { assert } from "../../logic/util/util";
  import { t } from "../../l10n/l10n";

  /** The address book for the new contact. null = the first one
   * in */
  export let selectedAddressbook: Addressbook | null;

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
</script>

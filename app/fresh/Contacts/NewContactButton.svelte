<NewContactButton {selectedAddressbook} let:addPerson>
  <Button
    label={$t`New contact`}
    icon={NewContactIcon}
    classes="primary new-contact"
    onClick={addPerson}
    />
</NewContactButton>

<script lang="ts">
  import type { Addressbook } from "../../logic/Contacts/Addressbook";
  import NewContactButton from "../../frontend/Contacts/NewContactButton.svelte";
  import Button from "../../frontend/Shared/Button.svelte";
  import NewContactIcon from "lucide-svelte/icons/user-plus";
  import { t } from "../../l10n/l10n";

  /** The address book for the new contact. null = the first one */
  export let selectedAddressbook: Addressbook | null;
</script>

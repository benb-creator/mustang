<WriteButton {account} {to} let:newMail>
  <Button
    label={$t`Write`}
    tooltip={$t`Write new email`}
    icon={WriteIcon}
    iconSize="16px"
    classes="primary"
    disabled={!account}
    onClick={newMail}
    />
</WriteButton>

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import type { PersonUID } from "../../../logic/Abstract/PersonUID";
  import WriteButton from "../../../frontend/Mail/LeftPane/WriteButton.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import WriteIcon from "lucide-svelte/icons/pencil-line";
  import { t } from "../../../l10n/l10n";

  export let account: MailAccount; /* in/out */
  export let to: PersonUID | null = null;
</script>

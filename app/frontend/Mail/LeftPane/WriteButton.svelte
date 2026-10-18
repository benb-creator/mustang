<Button
  label={$t`Write new email`}
  icon={WriteIcon}
  iconSize="16px"
  {iconOnly}
  classes="create filled"
  disabled={!account}
  onClick={newMail}
  />

<script lang="ts">
  import type { MailAccount } from "../../../logic/Mail/MailAccount";
  import { PersonUID } from "../../../logic/Abstract/PersonUID";
  import { mailMustangApp } from "../MailMustangApp";
  import Button from "../../Shared/Button.svelte";
  import WriteIcon from "lucide-svelte/icons/square-pen";
  import { assert } from "../../../logic/util/util";
  import { gt, t } from "../../../l10n/l10n";

  export let account: MailAccount; /* in/out */
  export let to: PersonUID | null = null;
  export let iconOnly = false;

  function newMail() {
    assert(account, gt`Please select a mail account first`);
    let email = account.newEMailFrom();
    if (to) {
      email.to.add(to);
    }
    mailMustangApp.writeMail(email);
  }
</script>

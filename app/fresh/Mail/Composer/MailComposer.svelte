<MailComposer {mail}>
  <svelte:fragment slot="send" let:sendDisabledTooltip let:onSend>
    <Button
      label={$t`Send`}
      icon={SendIcon}
      iconSize="16px"
      classes="primary"
      disabled={sendDisabledTooltip ?? false}
      onClick={onSend}
      tabindex={2}
      />
  </svelte:fragment>
</MailComposer>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import MailComposer from "../../../frontend/Mail/Composer/MailComposer.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import SendIcon from "lucide-svelte/icons/send";
  import { t } from "../../../l10n/l10n";

  export let mail: EMail;
</script>

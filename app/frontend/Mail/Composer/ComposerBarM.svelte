<hbox class="buttons">
  <AppBarM>
    <!-- left -->
    <hbox class="trash">
      <Button
        icon={TrashIcon}
        iconSize="24px"
        iconOnly
        label={$t`Delete this message`}
        onClick={deleteMessage}
        disabled={!message}
        plain
        />
    </hbox>

    <!-- left middle -->
    <hbox class="empty" />

    <AppMenuButton />

    <!-- right middle -->
    <hbox class="menu button">
      <ButtonMenu bind:isMenuOpen>
        <ComposerMenuM {message} />
      </ButtonMenu>
    </hbox>

    <!-- right -->
    <hbox class="send">
      <Button
        icon={SendIcon}
        iconSize="22px"
        iconOnly
        label={$t`Send`}
        onClick={send}
        selected={!sendDisabledReason}
        plain
        />
    </hbox>
  </AppBarM>
</hbox>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import ComposerMenuM from "./ComposerMenuM.svelte";
  import AppBarM from "../../AppsBar/AppBarM.svelte";
  import ButtonMenu from "../../Shared/Menu/ButtonMenu.svelte";
  import AppMenuButton from "../../AppsBar/AppMenuM/AppMenuButton.svelte";
  import Button from "../../Shared/Button.svelte";
  import TrashIcon from "lucide-svelte/icons/trash-2";
  import SendIcon from "lucide-svelte/icons/send";
  import { UserError } from "../../../logic/util/util";
  import { t } from "../../../l10n/l10n";

  export let message: EMail;
  export let onSend: () => Promise<void>;
  /** Why the mail can't be sent yet. null = ready to send */
  export let sendDisabledReason: string | null = null;

  /** Tells the reason, because there are no tooltips on mobile */
  async function send() {
    if (sendDisabledReason) {
      throw new UserError(sendDisabledReason);
    }
    await onSend();
  }

  async function deleteMessage() {
    await message.deleteMessage();
  }

  let isMenuOpen = false;
</script>

<style>
  .send :global(button) {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    justify-content: center;
  }
</style>

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
    <hbox class="move button">
      <Button
        icon={FolderActionsIcon}
        iconSize="24px"
        iconOnly
        label={$t`Move to folder, or add tag`}
        onClick={onPopupToggle}
        plain
        />
    </hbox>

    <AppMenuButton />

    <!-- right middle -->
    {#if message.isDraft || message.folder?.specialFolder == SpecialFolder.Drafts }
      <hbox class="draft">
        <Button
          icon={WriteIcon}
          iconSize="24px"
          iconOnly
          label={$t`Edit draft`}
          onClick={editDraft}
          plain
          />
      </hbox>
    {:else}
      <hbox class="reply">
        <Button
          icon={ReplyIcon}
          iconSize="24px"
          iconOnly
          label={$t`Reply to author`}
          onClick={reply}
          plain
          />
      </hbox>
    {/if}

    <!-- right -->
    <hbox class="menu button">
      <ButtonMenu bind:isMenuOpen>
        <MessageMenu bind:message {printE} />
        <hbox class="display-mode">
          <DisplayModeSwitcher />
        </hbox>
      </ButtonMenu>
    </hbox>
  </AppBarM>
</hbox>
<Menu bind:isMenuOpen={popupOpen} anchor={null}>
  <MessageMovePopup messages={new ArrayColl([message])} on:close={onPopupClose} />
</Menu>

<Print {message} bind:this={printE} />

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { mailMustangApp } from "../MailMustangApp";
  import { SpecialFolder } from "../../../logic/Mail/Folder";
  import { goTo, goBack } from "../../AppsBar/selectedApp";
  import MessageMenu from "./MessageMenu.svelte";
  import MessageMovePopup from "./MessageMovePopup.svelte";
  import Print from "./MessagePrint.svelte";
  import DisplayModeSwitcher from "./DisplayModeSwitcher.svelte";
  import AppBarM from "../../AppsBar/AppBarM.svelte";
  import ButtonMenu from "../../Shared/Menu/ButtonMenu.svelte";
  import AppMenuButton from "../../AppsBar/AppMenuM/AppMenuButton.svelte";
  import Menu from "../../Shared/Menu/Menu.svelte";
  import Button from "../../Shared/Button.svelte";
  import FolderIcon from "lucide-svelte/icons/folder";
  import ListIcon from "lucide-svelte/icons/list";
  import TrashIcon from "lucide-svelte/icons/trash-2";
  import ReplyIcon from "lucide-svelte/icons/reply";
  import WriteIcon from "lucide-svelte/icons/pencil";
  import FolderActionsIcon from "lucide-svelte/icons/folder-dot";
  import { ArrayColl } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let message: EMail;

  function goToAccounts() {
    goTo("/mail/", {});
  }
  async function deleteMessage() {
    await message.deleteMessage();
    goBack();
  }
  function reply() {
    let reply = message.compose.replyToAuthor();
    mailMustangApp.writeMail(reply);
  }
  async function editDraft() {
    await message.loadMIME();
    mailMustangApp.writeMail(message);
  }

  let isMenuOpen = false;
  let printE: Print;

  // Folder sheet
  let popupOpen = false;
  function onPopupToggle(event) {
    popupOpen = !popupOpen;
  }
  function onPopupClose() {
    popupOpen = false;
  }
</script>

<style>
  .menu :global(.island) {
    color: black;
    justify-content: center;
  }
  .display-mode {
    padding: 8px 16px 0px 16px;
  }
  .display-mode :global(.island) {
    flex: 1;
  }
  .display-mode :global(button) {
    flex: 1;
    height: 48px;
  }
  .display-mode :global(button svg) {
    width: 22px;
    height: 22px;
  }
</style>

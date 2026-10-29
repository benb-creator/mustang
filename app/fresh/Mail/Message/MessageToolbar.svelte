<MessageToolbar {message}
  let:recipients let:toggleRead let:toggleStar let:reply let:replyAll let:deleteMessage let:toggleSpam let:editDraft let:printE>
  <hbox class="message-toolbar">
    {#key message} <!-- Rebuild per mail, otherwise the spinner from the previous mail stays. -->
    {#if message.isDraft || message.folder?.specialFolder == SpecialFolder.Drafts }
      <Button
        icon={WriteIcon}
        iconSize="16px"
        label={$t`Edit draft`}
        onClick={editDraft}
        classes="primary"
        />
    {/if}
    <hbox class="group reply-group">
      <hbox class="reply">
        <Button
          icon={ReplyIcon}
          iconSize="16px"
          iconOnly={$appGlobal.isSmall}
          label={$t`Reply`}
          tooltip={$t`Reply to author`}
          shortCutInfo="{ctrl}+R"
          onClick={reply}
          />
      </hbox>
      {#if recipients.length > 1 && (message.bcc.isEmpty || message.outgoing)}
        <hbox class="in-menu">
          <Button
            icon={ReplyAllIcon}
            iconSize="16px"
            iconOnly
            label={$t`Reply to all`}
            shortCutInfo="{ctrl}+Shift+R"
            onClick={replyAll}
            plain
            />
        </hbox>
      {/if}
      <hbox class="in-menu">
        <Button
          icon={ForwardIcon}
          iconSize="16px"
          iconOnly
          label={$t`Forward`}
          tooltip={$t`Send this message to somebody else`}
          shortCutInfo="{ctrl}+L"
          onClick={(event: MouseEvent) => mailMustangApp.forward(message, !!event?.shiftKey)}
          plain
          />
      </hbox>
    </hbox>
    <hbox class="group">
      <hbox class="move" bind:this={moveE}>
        <Button
          icon={FolderActionsIcon}
          iconSize="16px"
          iconOnly
          label={$t`Move to folder, or add tag`}
          onClick={() => popupOpen = !popupOpen}
          plain
          />
      </hbox>
      <Button
        icon={TrashIcon}
        iconSize="16px"
        iconOnly
        label={$t`Delete this message`}
        shortCutInfo="Delete"
        onClick={deleteMessage}
        disabled={!message}
        plain
        />
      <Button
        icon={$message.isSpam ? NotSpamIcon : SpamIcon}
        iconSize="16px"
        iconOnly
        label={$message.isSpam ? $t`This email is *not* spam` : $t`Treat this email as spam: Move it to the Spam folder, and train the spam filter`}
        shortCutInfo={$message.isSpam ? "Shift+J" : "J"}
        onClick={toggleSpam}
        disabled={!message}
        plain
        />
    </hbox>
    <hbox class="group">
      <hbox class="unread" class:read={$message.isRead}>
        <Button
          icon={CircleIcon}
          iconSize="14px"
          iconOnly
          label={$message.isRead ? $t`Mark this message as unread` : $t`Mark this message as read`}
          shortCutInfo="M"
          onClick={toggleRead}
          plain
          />
      </hbox>
      <hbox class="star" class:starred={$message.isStarred}>
        <Button
          icon={StarIcon}
          iconSize="16px"
          iconOnly
          label={$t`Remember this message`}
          shortCutInfo="S"
          onClick={toggleStar}
          plain
          />
      </hbox>
    </hbox>
    {/key}
    <ButtonMenu label={$t`More actions`}>
      <MessageMenu {message} {printE} />
    </ButtonMenu>
  </hbox>
</MessageToolbar>
<Popup bind:popupOpen popupAnchor={moveE} placement="bottom" boundaryElSel=".message-display-pane">
  <MessageMovePopup messages={new ArrayColl([message])} on:close={() => popupOpen = false} />
</Popup>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { mailMustangApp } from "../../../frontend/Mail/MailMustangApp";
  import { SpecialFolder } from "../../../logic/Mail/Folder";
  import { appGlobal } from "../../../logic/app";
  import { getOSName } from "../../../frontend/Util/util";
  import MessageToolbar from "../../../frontend/Mail/Message/MessageToolbar.svelte";
  import MessageMenu from "../../../frontend/Mail/Message/MessageMenu.svelte";
  import MessageMovePopup from "../../../frontend/Mail/Message/MessageMovePopup.svelte";
  import ButtonMenu from "../../../frontend/Shared/Menu/ButtonMenu.svelte";
  import Popup from "../../../frontend/Shared/Popup.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import StarIcon from "lucide-svelte/icons/star";
  import CircleIcon from "lucide-svelte/icons/circle";
  import ReplyIcon from "lucide-svelte/icons/reply";
  import ReplyAllIcon from "lucide-svelte/icons/reply-all";
  import ForwardIcon from "lucide-svelte/icons/forward";
  import TrashIcon from "lucide-svelte/icons/trash-2";
  import SpamIcon from "lucide-svelte/icons/shield-x";
  import NotSpamIcon from "lucide-svelte/icons/shield-off";
  import WriteIcon from "lucide-svelte/icons/pencil";
  import FolderActionsIcon from "lucide-svelte/icons/folder-dot";
  import { ArrayColl } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  export let message: EMail;

  const ctrl = getOSName() == "macintosh" ? "Cmd" : "Ctrl";

  let moveE: HTMLElement;
  let popupOpen = false;
</script>

<style>
  .message-toolbar {
    flex: none;
    align-items: center;
    gap: 4px;
  }
  .group {
    align-items: center;
    gap: 2px;
  }
  .group + .group,
  .reply-group {
    padding-inline-start: 4px;
  }
  .group + .group::before {
    content: "";
    width: 1px;
    height: 16px;
    margin-inline-end: 4px;
    background-color: var(--border);
  }
  .reply {
    margin-inline-end: 2px;
  }
  .unread :global(svg) {
    color: var(--fg-2);
  }
  .unread:not(.read) :global(svg) {
    fill: var(--unread);
    color: var(--unread);
  }
  .star.starred :global(svg) {
    fill: var(--star);
    color: var(--star);
  }
  @container (max-width: 560px) {
    .reply-group :global(.button .label) {
      display: none;
    }
  }
  @container (max-width: 420px) {
    .in-menu {
      display: none;
    }
  }
</style>

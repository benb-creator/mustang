<!-- If you change the columns here, also change the `FastList.columns` in TableMessageList.svelte -->
<TableMessageListItem {message} popupAnchor={popupAnchorE}
  let:contactName let:toggleRead let:toggleStar let:toggleSpam let:deleteMessage let:onPopupToggle let:contextMenu>
  <hbox class="state"
    class:show-account={showAccount}
    class:direction-shown={hasDirection && $message.isRead}
    style="--account-color: {$message.folder.account.color}"
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    >
    {#if $message.isSending}
      <SendingIcon size="14px" class="sending" />
    {:else}
      {#if hasDirection}
        <hbox class="direction">
          {#if $message.outgoing}
            <OutgoingIcon size="14px" />
          {:else if $message.isReplied}
            <ReplyIcon size="14px" />
          {:else if $message.isForwarded}
            <ForwardIcon size="14px" />
          {:else if $message.isImportant}
            <ImportantIcon size="14px" class="important" />
          {/if}
        </hbox>
      {/if}
      <hbox class="unread-dot" class:unread={!$message.isRead}>
        {#key message} <!-- Rebuild per mail, otherwise the spinner from the previous mail stays. -->
        <Button
          icon={CircleIcon}
          iconSize="8px"
          iconOnly
          label={$message.isRead ? $t`Mark this message as unread` : $t`Mark this message as read`}
          onClick={toggleRead}
          plain
          classes="small"
          />
        {/key}
      </hbox>
    {/if}
  </hbox>
  <hbox class="attachment" on:contextmenu={event => contextMenu.onContextMenu(event)}>
    {#if $message.hasVisibleAttachments}
      <AttachmentIcon size="14px" />
    {/if}
  </hbox>
  <hbox class="correspondent"
    class:unread={!$message.isRead}
    draggable="true"
    on:dragstart={(event) => catchErrors(() => onDragStartMail(event, message))}
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    >{contactName}</hbox>
  <hbox class="subject-tags" on:contextmenu={event => contextMenu.onContextMenu(event)}>
    <hbox class="subject"
      class:unread={!$message.isRead}
      draggable="true"
      on:dragstart={(event) => catchErrors(() => onDragStartMail(event, message))}
      >{$message.subject}</hbox>
    {#if $tags.hasItems}
      <hbox class="tags">
        <TagSelector tags={$tags} object={message} canAdd={false} />
      </hbox>
    {/if}
    <hbox class="star" class:starred={$message.isStarred}>
      {#key message}
      <Button
        icon={StarIcon}
        iconSize="14px"
        iconOnly
        label={$t`Remember this message`}
        onClick={toggleStar}
        plain
        classes="small"
        />
      {/key}
    </hbox>
  </hbox>
  <hbox class="date-actions" on:contextmenu={event => contextMenu.onContextMenu(event)}>
    <hbox class="date"
      class:unread={!$message.isRead}
      draggable="true"
      on:dragstart={(event) => catchErrors(() => onDragStartMail(event, message))}
      title={$message.sent?.toLocaleString(getDateTimeLocale())}
      >{getDateTimeString($message.sent)}</hbox>
    <hbox class="actions">
      <hbox class="move" bind:this={popupAnchorE}>
        <Button
          icon={FolderActionsIcon}
          iconSize="14px"
          iconOnly
          label={$t`Move to folder, or add tag`}
          onClick={onPopupToggle}
          plain
          classes="small"
          />
      </hbox>
      {#key message}
      <Button
        icon={$message.isSpam ? NotSpamIcon : SpamIcon}
        iconSize="14px"
        iconOnly
        label={$message.isSpam ? $t`Mark as not spam` : $t`Mark as spam`}
        tooltip={$message.isSpam ? $t`This email is *not* spam` : $t`Treat this email as spam: Move it to the Spam folder, and train the spam filter`}
        onClick={toggleSpam}
        plain
        classes="small"
        />
      <Button
        icon={DeleteIcon}
        iconSize="14px"
        iconOnly
        label={$t`Delete this message`}
        onClick={deleteMessage}
        plain
        classes="small"
        />
      {/key}
    </hbox>
  </hbox>
</TableMessageListItem>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { onDragStartMail } from "../../../frontend/Mail/Message/drag";
  import TableMessageListItem from "../../../frontend/Mail/3pane/TableMessageListItem.svelte";
  import { selectedFolder } from "../../../frontend/Mail/Selected";
  import TagSelector from "../../../frontend/Shared/Tag/TagSelector.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import OutgoingIcon from "lucide-svelte/icons/arrow-big-left";
  import SendingIcon from "lucide-svelte/icons/send";
  import ReplyIcon from "lucide-svelte/icons/reply";
  import ForwardIcon from "lucide-svelte/icons/forward";
  import ImportantIcon from "lucide-svelte/icons/circle-alert";
  import StarIcon from "lucide-svelte/icons/star";
  import CircleIcon from "lucide-svelte/icons/circle";
  import AttachmentIcon from "lucide-svelte/icons/paperclip";
  import DeleteIcon from "lucide-svelte/icons/trash-2";
  import SpamIcon from "lucide-svelte/icons/shield-x";
  import NotSpamIcon from "lucide-svelte/icons/shield-off";
  import FolderActionsIcon from "lucide-svelte/icons/folder-dot";
  import { getDateTimeString } from "../../../logic/util/date";
  import { catchErrors } from "../../../frontend/Util/error";
  import { getDateTimeLocale, t } from "../../../l10n/l10n";

  export let message: EMail;

  $: hasDirection = $message.outgoing || $message.isReplied || $message.isForwarded || $message.isImportant;
  /** Search results and virtual folders mix folders and accounts */
  $: showAccount = $message.folder != $selectedFolder;

  $: tags = message.tags;

  let popupAnchorE: HTMLElement;
</script>

<style>
  .state,
  .attachment,
  .correspondent,
  .subject-tags,
  .date-actions {
    box-sizing: border-box;
    height: var(--list-row-height);
    align-items: center;
    min-width: 0;
    font-size: var(--text-m);
    color: var(--fg-1);
  }
  .state {
    position: relative;
    justify-content: center;
    padding: 0 !important; /* beats the padding of FastList row cells */
    padding-inline-start: 4px !important;
    color: var(--fg-3);
  }
  .state.show-account::before {
    content: "";
    position: absolute;
    inset-block: 6px;
    inset-inline-start: 0;
    width: 3px;
    background-color: var(--account-color);
  }
  .state.direction-shown .unread-dot,
  :global(.row:hover) .state.direction-shown .direction,
  .state:not(.direction-shown) .direction {
    display: none;
  }
  :global(.row:hover) .state.direction-shown .unread-dot {
    display: flex;
  }
  .state :global(svg.important) {
    color: var(--danger-fg);
  }
  .state :global(svg.sending) {
    animation: sending 1.5s linear infinite;
  }
  @keyframes sending {
    0% { opacity: 0%; transform: translate(-4px, 3px); animation-timing-function: ease-out; }
    20% { opacity: 100%; transform: translate(-2px, -1px); }
    80% { opacity: 100%; transform: translate(2px, -2px); animation-timing-function: ease-in; }
    100% { opacity: 0%; transform: translate(4px, -3px); }
  }
  @media (prefers-reduced-motion: reduce) {
    .state :global(svg.sending) {
      animation: none;
    }
  }
  .attachment {
    justify-content: center;
    padding: 0 !important;
    color: var(--fg-3);
  }
  .correspondent,
  .subject {
    display: block;
    line-height: var(--list-row-height);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .subject {
    flex: 1 1 0;
    min-width: 0;
    color: var(--fg-2);
  }
  .correspondent.unread,
  .subject.unread {
    font-weight: 600;
    color: var(--fg-1);
  }
  .subject-tags {
    gap: 6px;
  }
  .tags {
    flex: none;
    max-width: 40%;
    overflow: hidden;
  }
  .tags :global(.tag-list) {
    flex-wrap: nowrap;
  }
  .tags :global(.tag) {
    flex: none;
    margin: 0 2px;
  }
  .date-actions {
    justify-content: end;
    padding-inline-end: 12px !important;
  }
  .date {
    font-size: var(--text-s);
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .date.unread {
    color: var(--fg-1);
    font-weight: 600;
  }
  .actions {
    gap: 2px;
  }
  :global(.row:not(:hover)) .actions {
    display: none;
  }
  :global(.row:hover) .date {
    display: none;
  }
  .unread-dot :global(svg) {
    fill: none;
    stroke: var(--border-input);
  }
  .unread-dot.unread :global(svg) {
    fill: var(--unread);
    stroke: var(--unread);
  }
  :global(.row:not(:hover)) .unread-dot:not(.unread) :global(svg) {
    display: none;
  }
  .star :global(svg) {
    color: var(--fg-3);
  }
  .star.starred :global(svg) {
    fill: var(--star);
    color: var(--star);
  }
  :global(.row:not(:hover)) .star:not(.starred) {
    visibility: hidden;
  }
  :global(.fast-list:focus-within .row.selected) .unread-dot.unread :global(svg),
  :global(.fast-list:focus-within .row.selected) .star.starred :global(svg) {
    fill: currentColor;
    stroke: currentColor;
    color: inherit;
  }
</style>

<VerticalMessageListItem {message} popupAnchor={popupAnchorE}
  let:contactName let:toggleRead let:toggleStar let:toggleSpam let:deleteMessage let:onPopupToggle let:contextMenu>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <hbox class="message"
    class:unread={!$message.isRead}
    class:show-account={showAccount}
    draggable="true" on:dragstart={(event) => catchErrors(() => onDragStartMail(event, message))}
    style="--account-color: {$message.folder.account.color};"
    on:contextmenu={event => contextMenu.onContextMenu(event)}
    on:click
    >
    <hbox class="state" class:direction-shown={hasDirection && $message.isRead}>
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
    <vbox class="lines" flex>
      <hbox class="top-row">
        <hbox class="contact">{contactName}</hbox>
        {#if $tags.hasItems}
          <hbox class="tags">
            <TagSelector tags={$tags} object={message} canAdd={false} />
          </hbox>
        {/if}
        <hbox class="date" title={$message.sent?.toLocaleString(getDateTimeLocale())}>
          {getDateTimeString($message.sent)}
        </hbox>
        <hbox class="actions" bind:this={popupAnchorE}>
          <Button
            icon={FolderActionsIcon}
            iconSize="14px"
            iconOnly
            label={$t`Move, tag, or delete`}
            onClick={onPopupToggle}
            plain
            classes="small"
            />
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
      <hbox class="bottom-row">
        <hbox class="subject">{$message.subject}</hbox>
        {#if $message.hasVisibleAttachments}
          <hbox class="attachment">
            <AttachmentIcon size="14px" />
          </hbox>
        {/if}
        <hbox class="star" class:starred={$message.isStarred}>
          {#key message}
          <Button
            icon={StarIcon}
            iconSize="16px"
            iconOnly
            label={$t`Remember this message`}
            onClick={toggleStar}
            plain
            classes="small"
            />
          {/key}
        </hbox>
      </hbox>
    </vbox>
  </hbox>
</VerticalMessageListItem>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { onDragStartMail } from "../../../frontend/Mail/Message/drag";
  import VerticalMessageListItem from "../../../frontend/Mail/Vertical/VerticalMessageListItem.svelte";
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
  .message {
    position: relative;
    box-sizing: border-box;
    height: var(--list-row-2-height);
    align-items: stretch;
    padding: 0 12px 0 0 !important; /* beats the padding of FastList row cells */
    border-bottom: 1px solid var(--border-subtle);
    font-size: var(--text-m);
    line-height: var(--line-m);
    color: var(--fg-1);
  }
  .message.show-account::before {
    content: "";
    position: absolute;
    inset-block: 8px;
    inset-inline-start: 0;
    width: 3px;
    background-color: var(--account-color);
  }
  .state {
    flex: none;
    width: 28px;
    padding-block-start: 6px;
    justify-content: center;
    align-items: start;
    color: var(--fg-3);
  }
  .state .direction {
    height: 24px;
    align-items: center;
  }
  .state.direction-shown .unread-dot,
  :global(.row:hover) .state.direction-shown .direction {
    display: none;
  }
  :global(.row:hover) .state.direction-shown .unread-dot {
    display: flex;
  }
  .state:not(.direction-shown) .direction {
    display: none;
  }
  .state :global(svg.important) {
    color: var(--danger-fg);
  }
  .state :global(svg.sending) {
    margin-block-start: 5px;
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
  .lines {
    min-width: 0;
    justify-content: center;
    gap: 2px;
  }
  .top-row,
  .bottom-row {
    align-items: center;
    gap: 6px;
    min-width: 0;
    height: 24px;
  }
  .contact,
  .subject {
    display: block;
    flex: 1 1 0;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .contact {
    font-weight: 600;
  }
  .message.unread .contact {
    font-weight: 700;
  }
  .subject {
    color: var(--fg-2);
  }
  .message.unread .subject {
    color: var(--fg-1);
    font-weight: 600;
  }
  .tags {
    flex: 0 1 auto;
    max-width: 45%;
    overflow: hidden;
  }
  .tags :global(.tag-list) {
    flex-wrap: nowrap;
  }
  .tags :global(.tag) {
    flex: none;
    margin: 0 2px;
  }
  .date {
    flex: none;
    font-size: var(--text-s);
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .actions {
    flex: none;
    gap: 2px;
    margin-inline-end: -4px;
  }
  :global(.row:not(:hover)) .actions {
    display: none;
  }
  :global(.row:hover) .date {
    display: none;
  }
  .attachment {
    flex: none;
    color: var(--fg-3);
  }
  .star {
    flex: none;
    margin-inline-end: -4px;
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
  .unread-dot :global(svg) {
    fill: none;
    stroke: var(--border-input);
  }
  .unread-dot.unread :global(svg) {
    fill: var(--unread);
    stroke: var(--unread);
  }
  :global(.row:not(:hover)) .unread-dot:not(.unread) :global(svg) {
    visibility: hidden;
  }
  :global(.fast-list:focus-within .row.selected) .unread-dot.unread :global(svg),
  :global(.fast-list:focus-within .row.selected) .star.starred :global(svg) {
    fill: currentColor;
    stroke: currentColor;
    color: inherit;
  }
</style>

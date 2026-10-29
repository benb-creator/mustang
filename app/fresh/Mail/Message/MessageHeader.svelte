<MessageHeader bind:message bind:isEncryptionExpanded let:onTagRemove>
  <PaneHeader level="l3" tall>
    <vbox flex class="message-header" class:outgoing={$message.outgoing}>
      <hbox class="sender-row">
        {#if $message.contact instanceof Person && $message.contact.picture}
          <hbox class="picture">
            <PersonPicture person={$message.contact} size={32} />
          </hbox>
        {/if}
        <hbox class="from">
          {#if $message.outgoing}
            <value class="me" title={$message.from.emailAddress}>
              {$t`me *=> myself as sender of the email`}
            </value>
          {:else}
            <Recipient recipient={$message.from} />
          {/if}
        </hbox>
        <EncryptionButtons {message} bind:isExpanded={isEncryptionExpanded} />
        <hbox class="toolbar">
          <MessageToolbar {message} />
        </hbox>
      </hbox>
      <value class="subject">{$message.subject}</value>
      <hbox class="recipients-row">
        <grid class="recipients">
          {#if $message.to.hasItems}
            <hbox class="label">{$t`to`}</hbox>
            <hbox class="list"><RecipientsList recipients={$message.to} /></hbox>
          {/if}
          {#if $message.cc.hasItems}
            <hbox class="label">{$t`cc`}</hbox>
            <hbox class="list"><RecipientsList recipients={$message.cc} /></hbox>
          {/if}
          {#if $message.bcc.hasItems}
            <hbox class="label">{$t`bcc`}</hbox>
            <hbox class="list"><RecipientsList recipients={$message.bcc} /></hbox>
          {/if}
        </grid>
        <hbox flex />
        <value class="date" title={$message.sent?.toLocaleString(getDateTimeLocale())}>
          {getDateTimeString($message.sent)}
        </value>
        {#if !$appGlobal.isSmall}
          <hbox class="display-mode">
            <DisplayModeSwitcher />
          </hbox>
        {/if}
      </hbox>
      {#if $tags.hasItems}
        <hbox class="tags">
          <TagSelector tags={$tags} object={message} canAdd={false}>
            <Button
              slot="tag-button"
              let:tag
              label={$t`Remove`}
              onClick={() => onTagRemove(tag)}
              icon={RemoveIcon}
              iconSize="12px"
              iconOnly
              plain
              classes="small remove"
              />
          </TagSelector>
        </hbox>
      {/if}
      {#if isEncryptionExpanded}
        <hbox class="encryption-details">
          <EncryptionDetails {message} bind:isExpanded={isEncryptionExpanded} />
        </hbox>
      {/if}
      {#if message.to.isEmpty || message.from.emailAddress == kDummyPerson.emailAddress}
        {#await message.loadForDisplay()}
          <!-- Subject etc. are loaded by search,
            and body is loaded by MessageBody calling message.loadBody(),
            but not to/from etc. -->
        {:catch ex}
          <ErrorMessageInline {ex} />
        {/await}
      {/if}
    </vbox>
  </PaneHeader>
</MessageHeader>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { Person } from "../../../logic/Abstract/Person";
  import { appGlobal } from "../../../logic/app";
  import { kDummyPerson } from "../../../logic/Abstract/PersonUID";
  import MessageHeader from "../../../frontend/Mail/Message/MessageHeader.svelte";
  import MessageToolbar from "./MessageToolbar.svelte";
  import RecipientsList from "../../../frontend/Mail/Message/RecipientsList.svelte";
  import Recipient from "../../../frontend/Mail/Message/Recipient.svelte";
  import PersonPicture from "../../../frontend/Contacts/Person/PersonPicture.svelte";
  import DisplayModeSwitcher from "../../../frontend/Mail/Message/DisplayModeSwitcher.svelte";
  import TagSelector from "../../../frontend/Shared/Tag/TagSelector.svelte";
  import EncryptionButtons from "../../../frontend/Mail/Message/EncryptionButtons.svelte";
  import EncryptionDetails from "../../../frontend/Mail/Message/EncryptionDetails.svelte";
  import ErrorMessageInline from "../../../frontend/Shared/ErrorMessageInline.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import PaneHeader from "../../Shared/PaneHeader.svelte";
  import RemoveIcon from "lucide-svelte/icons/x";
  import { getDateTimeString } from "../../../logic/util/date";
  import { getDateTimeLocale, t } from "../../../l10n/l10n";

  export let message: EMail;

  $: tags = message.tags;
  let isEncryptionExpanded = false;
</script>

<style>
  .message-header {
    gap: 8px;
    min-width: 0;
  }
  .sender-row {
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    min-width: 0;
    min-height: 32px;
  }
  .toolbar {
    margin-inline-start: auto;
  }
  .picture {
    flex: none;
  }
  .from {
    flex: 0 1 auto;
    min-width: 96px;
    font-size: var(--text-l);
    line-height: var(--line-l);
    font-weight: 600;
    color: var(--fg-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .from :global(.domain) {
    font-weight: 400;
    font-style: normal;
    font-size: var(--text-s);
    color: var(--fg-2);
  }
  .outgoing .me {
    font-weight: 400;
    color: var(--fg-2);
  }
  .subject {
    display: block;
    font-size: var(--text-2xl);
    line-height: var(--line-2xl);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg-1);
    overflow-wrap: anywhere;
    user-select: text;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .recipients-row {
    align-items: start;
    gap: 12px;
    min-width: 0;
  }
  .recipients {
    grid-template-columns: max-content minmax(0, 1fr);
    column-gap: 8px;
    row-gap: 2px;
    min-width: 0;
    font-size: var(--text-m);
    line-height: 24px;
    color: var(--fg-1);
  }
  .recipients .label {
    min-width: 24px;
    font-size: var(--text-s);
    font-weight: 600;
    color: var(--fg-3);
    text-transform: capitalize;
  }
  .recipients .list {
    min-width: 0;
  }
  .recipients .list :global(.persons) {
    flex-wrap: wrap;
    font-size: var(--text-m);
  }
  .outgoing .recipients {
    font-weight: 600;
  }
  .date {
    flex: none;
    font-size: var(--text-s);
    line-height: 24px;
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .display-mode {
    flex: none;
  }
  .tags {
    flex-wrap: wrap;
  }
  .tags :global(.tag .button.button) {
    width: 16px;
    min-width: 16px;
    height: 16px;
    min-height: 16px;
    padding: 0;
  }
  .encryption-details {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    background-color: var(--l2-bg);
  }
  @container (max-width: 560px) {
    .display-mode {
      display: none;
    }
  }
</style>

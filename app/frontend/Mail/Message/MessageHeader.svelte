<vbox class="message-header"
  class:outgoing={$message.outgoing}
  on:swipeleft={onPreviousMessage}
  on:swiperight={onNextMessage}
  >
  <hbox class="toolbar-row">
    {#if !$appGlobal.isSmall}
      <vbox class="display-mode">
        <DisplayModeSwitcher />
      </vbox>
    {/if}
    <hbox flex />
    <MessageToolbar {message} />
  </hbox>
  <hbox class="subject-line">
    <value class="subject">{$message.subject}</value>
  </hbox>
  <hbox class="correspondents">
    {#if $message.contact instanceof Person && $message.contact.picture}
      <vbox class="picture">
        <PersonPicture person={$message.contact} size={40} />
      </vbox>
    {/if}
    <vbox flex class="people">
      <hbox class="from-line">
        <hbox class="from">
          {#if $message.outgoing}
            <value class="from" title={$message.from.emailAddress}>
              {$t`me *=> myself as sender of the email`}
            </value>
          {:else}
            <Recipient recipient={$message.from} />
          {/if}
          <EncryptionButtons {message} bind:isExpanded={isEncryptionExpanded} />
        </hbox>
        <hbox flex />
        <value class="date font-small" title={$message.sent?.toLocaleString(getDateTimeLocale())}>
          {getDateTimeString($message.sent)}
        </value>
      </hbox>
      <vbox class="recipients">
        {#if $message.to.hasItems}
          <hbox class="to font-small">
            <hbox class="label">{$t`to`}</hbox>
            <RecipientsList recipients={$message.to} />
          </hbox>
        {/if}
        {#if $message.cc.hasItems}
          <hbox class="cc font-small">
            <hbox class="label">{$t`cc`}</hbox>
            <RecipientsList recipients={$message.cc} />
          </hbox>
        {/if}
        {#if $message.bcc.hasItems}
          <hbox class="bcc font-small">
            <hbox class="label">{$t`bcc`}</hbox>
            <RecipientsList recipients={$message.bcc} />
          </hbox>
        {/if}
      </vbox>
    </vbox>
  </hbox>
  {#if isEncryptionExpanded}
    <EncryptionDetails {message} bind:isExpanded={isEncryptionExpanded} />
  {/if}
  {#if $tags.hasItems}
    <hbox class="tags">
      <TagSelector tags={$tags} object={message} canAdd={false}>
        <RoundButton
          slot="tag-button"
          let:tag
          label={$t`Remove`}
          onClick={() => onTagRemove(tag)}
          icon={RemoveIcon}
          classes="small remove"
          iconSize="12px"
          padding="0px"
          border={false}
          />
      </TagSelector>
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

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { PersonUID, kDummyPerson } from "../../../logic/Abstract/PersonUID";
  import { Person } from "../../../logic/Abstract/Person";
  import type { PersonOrGroup } from "../../Contacts/Person/PersonOrGroup";
  import { selectedPerson } from "../../Contacts/Person/Selected";
  import type { Tag } from "../../../logic/Abstract/Tag";
  import { appGlobal } from "../../../logic/app";
  import MessageToolbar from "./MessageToolbar.svelte";
  import RecipientsList from "./RecipientsList.svelte";
  import Recipient from "./Recipient.svelte";
  import PersonPicture from "../../Contacts/Person/PersonPicture.svelte";
  import DisplayModeSwitcher from "./DisplayModeSwitcher.svelte";
  import TagSelector from "../../Shared/Tag/TagSelector.svelte";
  import EncryptionButtons from "./EncryptionButtons.svelte";
  import EncryptionDetails from "./EncryptionDetails.svelte";
  import ErrorMessageInline from "../../Shared/ErrorMessageInline.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import RemoveIcon from "lucide-svelte/icons/x";
  import { getLocalStorage } from "../../Util/LocalStorage";
  import { catchErrors, backgroundError } from "../../Util/error";
  import { getDateTimeString } from "../../Util/date";
  import { getDateTimeLocale, t } from "../../../l10n/l10n";
  import { onDestroy } from "svelte";

  export let message: EMail;

  $: tags = message.tags;

  let readDelaySetting = getLocalStorage("mail.read.after", 0); // 0 = Immediately; -1 = Manually; 1 to 20 = delay in seconds
  $: readDelay = $readDelaySetting.value;
  $: catchErrors(() => markMessageAsRead(message, readDelay), backgroundError);
  let readTimeout: NodeJS.Timeout;
  function markMessageAsRead(message: EMail, readDelay: number) {
    if (message.isRead) {
      return;
    }
    if (readDelay < 0) {
      return;
    }
    if (readDelay == 0) {
      readDelay = 0.2; // Avoid that normal scrolling marks all msgs as read
    }
    clearTimeout(readTimeout);
    readTimeout = setTimeout(() => {
      message.markRead(true)
        .catch(message.folder.account.errorCallback);
    }, readDelay * 1000);
  }
  onDestroy(() => {
    clearTimeout(readTimeout);
  });

  let isEncryptionExpanded = false;
  $: $message, closeEncryption()
  function closeEncryption() {
    isEncryptionExpanded = false;
  }

  // TODO Duplicated in MailApp.svelte
  $: selectPerson(message?.contact);
  function selectPerson(contact: PersonOrGroup | PersonUID) {
    if (contact instanceof PersonUID) {
      contact = contact.findPerson();
    }
    if (!(contact instanceof Person)) {
      return;
    }
    $selectedPerson = contact;
  }

  async function onTagRemove(tag: Tag) {
    await message.removeTag(tag);
  }

  function onNextMessage() {
    message = message.nextMessage(false);
  }
  function onPreviousMessage() {
    message = message.nextMessage(true);
  }
</script>

<style>
  .message-header {
    padding: 0px 20px 12px 20px;
    border-block-end: 1px solid var(--border);
    background-color: var(--main-bg);
    color: var(--main-fg);
    z-index: 1;
  }
  .toolbar-row {
    height: var(--pane-header-height);
    min-height: var(--pane-header-height);
    align-items: center;
    margin-inline: -12px -12px;
  }
  .toolbar-row :global(.buttons) {
    margin-block-end: 0px;
  }
  .subject-line {
    margin-block: 4px 12px;
  }
  .subject {
    font-size: 20px;
    font-weight: 600;
    line-height: 1.3;
  }
  .correspondents {
    align-items: start;
  }
  .picture {
    margin-inline-end: 12px;
  }
  .from-line {
    align-items: baseline;
  }
  .from {
    font-weight: 600;
    align-items: center;
  }
  .from :global(.domain) {
    font-weight: normal;
    color: var(--fg-muted);
  }
  .outgoing .from {
    font-weight: normal;
    color: var(--fg-muted);
  }
  .recipients {
    margin-block-start: 2px;
  }
  .recipients .label {
    margin-block-start: 2px;
    margin-inline-end: 6px;
    color: var(--fg-faint);
  }
  .to,
  .cc,
  .bcc {
    color: var(--fg-muted);
  }
  .outgoing .to {
    font-weight: 600;
    color: inherit;
  }
  .date {
    margin-inline-start: 16px;
    color: var(--fg-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .tags {
    margin-block-start: 8px;
  }
  .message-header :global(.error) {
    margin-inline: -4px -12px;
  }
  @media (max-width: 600px)  {
    .message-header {
      padding: 0px 8px 8px 16px;
    }
    .subject {
      font-size: 17px;
    }
  }
</style>

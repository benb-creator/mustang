<!-- Appears below the msg list -->
 {#if folder}
  <hbox class="folder-header font-smallest">
    {#if showGetMail && $account?.isLoggedIn}
      <GetMailButton {folder} />
    {/if}
    <hbox class="buttons">
      <hbox class="attachment button" class:on={$quickSearch.hasAttachment}>
        <RoundButton
          icon={AttachmentIcon}
          iconSize={$appGlobal.isMobile ? "20px" : "14px"}
          label={$t`Show only messages with attachments`}
          onClick={toggleAttachments}
          selected={$quickSearch.hasAttachment}
          border={false}
          />
      </hbox>
      <hbox class="star button" class:starred={$quickSearch.isStarred}>
        <RoundButton
          icon={StarIcon}
          iconSize={$appGlobal.isMobile ? "24px" : "16px"}
          label={$t`Show only starred messages`}
          onClick={toggleStarred}
          selected={$quickSearch.isStarred}
          border={false}
          />
      </hbox>
      <hbox class="unread-dot button" class:unread={$quickSearch.isRead === false}>
        <RoundButton
          icon={CircleIcon}
          iconSize={$appGlobal.isMobile ? "18px" : "10px"}
          padding="11px"
          label={$t`Show only unread messages`}
          onClick={toggleUnread}
          selected={$quickSearch.isRead === false}
          border={false}
          />
      </hbox>
      {#if !isShowSearchField}
        <hbox class="show-search button">
        <RoundButton
            icon={SearchIcon}
            iconSize={$appGlobal.isMobile ? "24px" : "16px"}
            label={$t`Search only the currently displayed folder for a keyword`}
            onClick={toggleShowSearchField}
            border={false}
            />
        </hbox>
      {/if}
    </hbox>
    {#if isShowSearchField}
      <SearchField bind:searchTerm={quickSearch.bodyText}
        on:clear={toggleShowSearchField}
        placeholder={$t`Search only this folder`}
        showX={true}
        autofocus={true} />
      <hbox class="result-msg-count">
        {#if searchMessages}
          {$searchMessages.length}
        {/if}
      </hbox>
    {:else if !appGlobal.isMobile}
      <Clickable onClick={toggleShowSearchField}>
        <hbox flex class="no-search" />
      </Clickable>
      <FolderMsgCount {folder} {searchMessages} />
    {/if}
  </hbox>
{/if}

<script lang="ts">
  import type { Folder } from '../../../logic/Mail/Folder';
  import type { EMail } from '../../../logic/Mail/EMail';
  import { quickSearch } from '../Selected';
  import { appGlobal } from '../../../logic/app';
  import FolderMsgCount from './FolderMsgCount.svelte';
  import SearchField from '../../Shared/SearchField.svelte';
  import GetMailButton from './GetMailButton.svelte';
  import RoundButton from '../../Shared/RoundButton.svelte';
  import Clickable from "../../Shared/Clickable.svelte";
  import SearchIcon from "lucide-svelte/icons/search";
  import StarIcon from "lucide-svelte/icons/star";
  import CircleIcon from "lucide-svelte/icons/circle";
  import AttachmentIcon from "lucide-svelte/icons/paperclip";
  import { catchErrors, showError } from '../../Util/error';
  import type { ArrayColl } from 'svelte-collections';
  import { t } from '../../../l10n/l10n';

  export let folder: Folder;
  export let searchMessages: ArrayColl<EMail> | null; /** out */
  export let showGetMail = true;

  $: account = folder?.account;

  let isShowSearchField = quickSearch.hasSearch();
  function toggleShowSearchField() {
    isShowSearchField = !isShowSearchField;
    if (!isShowSearchField) {
      clearSearch();
    }
  }

  function toggleStarred() {
    quickSearch.isStarred = quickSearch.isStarred ? null : true;
  }
  function toggleUnread() {
    quickSearch.isRead = quickSearch.isRead === false ? null : false;
  }
  function toggleAttachments() {
    quickSearch.hasAttachment = quickSearch.hasAttachment ? null : true;
  }

  $: quickSearch.folder = folder;
  $: folder && $quickSearch && catchErrors(startSearch, showError);

  /** Filters the folder.messages array */
  async function startSearch() {
    searchMessages = await quickSearch.startSearch();
  }

  function clearSearch() {
    quickSearch.reset();
    searchMessages = null;
  }
</script>

<style>
  .folder-header {
    align-items: center;
    justify-content: center;
    max-height: 32px;
    padding-block-start: 2px;
    padding-block-end: 2px;
    padding-inline-start: 4px;
    padding-inline-end: 4px;
    overflow: hidden;
  }
  :global(.mobile) .folder-header {
    height: 32px;
    max-height: 32px;
    font-size: 16px;
  }
  .buttons {
    align-items: center;
  }
  .folder-header :global(button) {
    background-color: unset;
    color: unset;
    margin-inline-start: -2px;
  }
  .folder-header :global(button:hover) {
    z-index: 1;
  }
  .folder-header :global(.get-mail button) {
    height: 20px;
    width: 20px;
    border: none;
    margin-inline-end: 8px;
  }
  :global(.mobile) .folder-header :global(.get-mail button) {
    height: 32px;
    width: 32px;
  }
  .folder-header :global(.star button svg) {
    stroke-width: 1.5px;
  }
  .folder-header :global(.search) {
    flex: 1 0 0;
    height: 100%;
    margin-inline-start: 8px;
    margin-inline-end: 8px;
  }
  .folder-header :global(input[type="search"]) {
    font-size: 15px;
  }
  :global(.mobile) .folder-header :global(.search),
  :global(.mobile) .folder-header :global(input[type="search"]) {
    height: 32px;
  }
  .result-msg-count {
    align-items: center;
    justify-content: end;
    padding-inline-start: 4px;
    padding-inline-end: 8px;
    opacity: 70%;
    min-width: 1.5em;
  }
  .no-search {
    height: 100%;
  }
  .attachment:not(.on) {
    opacity: 80%;
  }
  .star.starred :global(svg) {
    fill: orange;
  }
  .unread-dot.unread :global(svg) {
    fill: green;
  }
  :global(.fresh) .folder-header {
    flex: 1 1 0;
    justify-content: end;
    gap: 4px;
    min-width: 0;
    max-height: none;
    padding: 0;
    overflow: visible;
    font-size: var(--text-m);
  }
  :global(.fresh) .folder-header :global(.msg-count) {
    order: -3;
    flex: 0 1 auto;
  }
  :global(.fresh) .folder-header :global(div:has(> .no-search)) {
    display: contents;
  }
  :global(.fresh) .no-search {
    order: -2;
    flex: 1 1 0;
    align-self: stretch;
    height: auto;
  }
  :global(.fresh) .folder-header :global(.search) {
    order: -2;
    flex: 1 1 0;
    height: auto;
    margin: 0;
  }
  :global(.fresh) .folder-header :global(input[type="search"]) {
    font-size: var(--text-m);
  }
  :global(.fresh) .result-msg-count {
    order: -1;
    padding: 0;
    opacity: 1;
    font-size: var(--text-s);
    color: var(--fg-2);
    font-variant-numeric: tabular-nums;
  }
  :global(.fresh) .buttons {
    gap: 2px;
  }
  :global(.fresh) .folder-header :global(.button.button) {
    margin: 0;
  }
  :global(.fresh) .unread-dot {
    order: 1;
  }
  :global(.fresh) .star {
    order: 2;
  }
  :global(.fresh) .attachment {
    order: 3;
  }
  :global(.fresh) .show-search {
    order: 4;
  }
  :global(.fresh) .attachment:not(.on) {
    opacity: 1;
  }
  :global(.fresh) .star.starred :global(svg) {
    fill: var(--star);
    color: var(--star);
  }
  :global(.fresh) .unread-dot :global(svg) {
    color: var(--fg-2);
  }
  :global(.fresh) .unread-dot.unread :global(svg) {
    fill: var(--unread);
    color: var(--unread);
  }
</style>

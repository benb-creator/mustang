<vbox flex class="search">
  <hbox class="header-bar">
    <hbox class="header top">{$t`Search`}</hbox>
    <hbox flex />
    <hbox class="buttons top-right">
      <RoundButton icon={XIcon} iconSize="16px" padding="4px" border={true} classes="small"
        onClick={onClear} />
    </hbox>
  </hbox>

  <Scroll>
    <hbox class="term font-normal">
      {$t`Search for`}
      <SearchField bind:searchTerm={$globalSearchTerm}
        placeholder={$t`File name or content`}
        bind:this={searchFieldEl} />
    </hbox>
    <hbox class="search-criteria">
      <SearchCriteria {search} showSearchTerm={false} />
    </hbox>
  </Scroll>

  <hbox class="results-count">
    {#if listAll?.length > kLimit}
      {$t`More than ${kLimit} files`}
    {:else if listAll}
      {$t`${listAll?.length} files`}
    {/if}
  </hbox>
</vbox>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { Directory } from "../../../logic/Files/Directory";
  import type { FileOrDirectory } from "../../../logic/Files/FileOrDirectory";
  import { newSearchFile } from "../../../logic/Files/Store/setStorage";
  import { globalSearchTerm } from "../../AppsBar/selectedApp";
  import { selectedFile } from "../selected";
  import SearchCriteria from "./SearchCriteria.svelte";
  import SearchField from "../../Shared/SearchField.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import XIcon from "lucide-svelte/icons/x";
  import { showError } from "../../Util/error";
  import { ArrayColl, Collection } from "svelte-collections";
  import debounce from "lodash/debounce";
  import { t } from "../../../l10n/l10n";
  import { createEventDispatcher, onMount } from 'svelte';
  const dispatchEvent = createEventDispatcher<{ clear: void }>();

  /** The search result
   * in/out */
  export let listFiles: Collection<File> | null = null;
  export let listDirs: Collection<Directory> | null = null;

  let listAll: Collection<FileOrDirectory> | null = null;
  let isOpen = true;
  const kLimit = 200;
  let search = newSearchFile();
  let tags = search.tags;
  let attachmentTypes = search.hasMIMETypes;

  if ($globalSearchTerm == null) {
    $globalSearchTerm = "";
  }

  $: search.contentText = $globalSearchTerm;
  $: isOpen, $globalSearchTerm, $search, $tags, $attachmentTypes, startSearchDebounced();
  const startSearchDebounced = debounce(() => startSearch(), 300);
  let lastCriteria: string;
  async function startSearch() {
    try {
      let criteria = JSON.stringify(search.toJSON());
      if (criteria == lastCriteria) {
        return; // backstop to break loops
      }
      lastCriteria = criteria;
      $selectedFile = null;
      listFiles = new ArrayColl<File>();
      listDirs = new ArrayColl<Directory>();

      let result = await search.startSearch(kLimit + 1);
      if (!isOpen) {
        return;
      }
      listAll = result;
      listDirs = result.filterObservable(f => f instanceof Directory) as any as Collection<Directory>;
      listFiles = result.filterObservable(f => f instanceof File) as any as Collection<File>;
      $selectedFile = listDirs.first ?? listFiles.first;
    } catch (ex) {
      showError(ex);
    }
  }

  function onClear() {
    isOpen = false;
    $globalSearchTerm = null;
    listFiles = null;
    listDirs = null;
    dispatchEvent("clear");
  }

  // window title | search field | (x) button
  $: if ($globalSearchTerm == null) dispatchEvent("clear");

  let searchFieldEl: SearchField;
  onMount(() => {
    if (!$globalSearchTerm) {
      searchFieldEl.focus();
    }
  });
</script>

<style>
  .search {
    margin: 8px 0px 12px 24px;
  }
  .header-bar {
    margin-inline-end: 8px;
  }
  .header.top {
    margin-block-start: 8px;
  }
  .header {
    font-size: 20px;
    font-weight: bold;
  }
  .buttons.top-right {
    align-items: start;
  }
  .term {
    margin: 8px 0px;
    align-items: center;
  }
  .term :global(.search) {
    margin: 0px 8px;
  }
  .term :global(input) {
    font-size: 16px;
  }
  .search-criteria {
    margin: 8px 0px 12px 24px;
  }
  .results-count {
    margin: 12px 24px;
    justify-content: end;
  }
  :global(.fresh) .search {
    min-height: 0;
    margin: 0;
    padding: 0 12px 12px;
  }
  :global(.fresh) .header-bar {
    align-items: center;
    min-height: var(--control-height-l);
    margin: 0;
  }
  :global(.fresh) .header.top {
    margin: 0;
  }
  :global(.fresh) .header {
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: var(--fg-1);
  }
  :global(.fresh) .buttons.top-right {
    align-items: center;
  }
  :global(.fresh) .term {
    flex-wrap: wrap;
    gap: 4px 8px;
    margin: 8px 0;
    color: var(--fg-2);
  }
  :global(.fresh) .term :global(.search) {
    flex: 1 1 140px;
    margin: 0;
  }
  :global(.fresh) .term :global(input) {
    font-size: var(--text-m);
  }
  :global(.fresh) .search-criteria {
    margin: 8px 0 12px;
  }
  :global(.fresh) .results-count {
    margin: 8px 0 0;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
  }
</style>

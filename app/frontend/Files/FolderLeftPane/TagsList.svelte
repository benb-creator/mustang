<vbox class="tags">
  <hbox class="header font-smallest">{$t`Tags`}</hbox>
  <vbox class="list">
    <TagSelector tags={availableTags} {selectedTags} canAdd={false}
      on:select={() => catchErrors(onSelect)}
      on:unselect={() => catchErrors(onSelect)}
      />
  </vbox>
</vbox>

<script lang="ts">
  import type { FileOrDirectory } from '../../../logic/Files/FileOrDirectory';
  import { Directory } from '../../../logic/Files/Directory';
  import { availableTags, type Tag } from '../../../logic/Abstract/Tag';
  import TagSelector from '../../Shared/Tag/TagSelector.svelte';
  import { catchErrors } from '../../Util/error';
  import { SetColl, Collection } from 'svelte-collections';
  import { t } from '../../../l10n/l10n';
  import { createEventDispatcher, onDestroy } from 'svelte';
  const dispatchEvent = createEventDispatcher<{ clear: void }>();

  export let selectedTags = new SetColl<Tag>();
  export let folder: Directory;
  export let searchFiles: Collection<FileOrDirectory> | null = null;

  $: folder, catchErrors(onSelect);

  async function onSelect() {
    if (selectedTags.hasItems) {
      let search = null; // TODO newSearchFiles();
      search.folder = folder;
      search.tags.replaceAll(selectedTags);
      searchFiles = await search.startSearch();
    } else {
      clear();
    }
  }

  function clear() {
    searchFiles = null;
    dispatchEvent("clear");
  }

  onDestroy(clear)
</script>

<style>
  .tags :global(.row hbox) {
    font-size: 14px;
  }
  .header {
    padding-inline-start: 10px !important;
    color: grey;
  }
  .list {
    margin-block-start: 8px;
    margin-inline-start: 10px;
  }
  :global(.fresh) .tags .header {
    box-sizing: border-box;
    height: var(--section-header-height);
    align-items: center;
    gap: 8px;
    margin-inline: 2px 12px;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
  }
  :global(.fresh) .tags .header::after {
    content: "";
    flex: 1 1 0;
    height: 1px;
    background-color: var(--border);
  }
  :global(.fresh) .list {
    margin: 4px 12px 0;
  }
</style>

<vbox flex class="folder-list">
  <FastTree items={foldersSorted} bind:selectedItem={selectedFolder} bind:selectedItems={selectedFolders}
    columns="auto">
    <svelte:fragment slot="header">
      <slot name="header">
        <hbox class="header font-smallest">{$t`Folders`}</hbox>
      </slot>
    </svelte:fragment>
    <svelte:fragment slot="row" let:item={folder} let:indentionLevel>
      <slot name="row" {folder} {indentionLevel}>
        <TreeItemLine item={folder}>
          <FolderLine {folder} slot="row" on:click>
            <slot name="buttons" slot="buttons" let:folder {folder} />
          </FolderLine>
        </TreeItemLine>
      </slot>
    </svelte:fragment>
  </FastTree>
</vbox>

<script lang="ts">
  import type { Folder } from '../../../logic/Mail/Folder';
  import FastTree from '../../Shared/FastTree.svelte';
  import type { Collection, ArrayColl } from 'svelte-collections';
  import FolderLine from './FolderLine.svelte';
  import TreeItemLine from '../../Shared/FastTreeItem.svelte';
  import { t } from '../../../l10n/l10n';

  export let folders: Collection<Folder>;
  export let selectedFolder: Folder; /* in/out */
  export let selectedFolders: ArrayColl<Folder>;

  $: foldersSorted = $folders.sortBy(f => f.orderPos);
</script>

<style>
  .header {
    padding-inline-start: 10px !important;
    color: grey;
  }
  :global(.fresh) .header {
    padding-inline-start: 12px !important; /* beats the !important above */
    font-size: var(--text-s);
    font-weight: 600;
    color: var(--fg-2);
  }
</style>

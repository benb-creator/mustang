<vbox class="recent-files-list">
  <FastList items={recentFiles} bind:selectedItem columns="1fr">
    <svelte:fragment slot="header">
      <hbox class="header">
        <hbox class="header-label font-smallest">{$t`Recent files`}</hbox>
        <hbox flex />
        <slot name="top-right" />
      </hbox>
    </svelte:fragment>
    <svelte:fragment slot="row" let:item={file}>
      <RecentListItem {file} />
    </svelte:fragment>
  </FastList>
</vbox>

<script lang="ts">
  import { File } from "../../../logic/Files/File";
  import { viewFile } from "../selected";
  import RecentListItem from "./RecentListItem.svelte";
  import FastList from "../../Shared/FastList.svelte";
  import { ArrayColl } from "svelte-collections";
  import { t } from "../../../l10n/l10n";

  let selectedItem: File | null = null;
  $: if (selectedItem) { $viewFile = selectedItem; }

  let recentFiles = new ArrayColl<File>(); // TODO
</script>

<style>
  .account-list :global(.fast-list) {
    overflow: inherit;
  }
  .account-list :global(.row hbox) {
    font-size: 14px;
  }
  .header {
    align-items: end;
    margin-block-start: 8px;
    margin-inline-start: 4px;
  }
  .header-label {
    color: grey;
  }
  .header :global(button) {
    margin-inline-start: 4px;
  }
  :global(.fresh) .recent-files-list {
    flex: 1 1 0;
    min-height: 0;
  }
  :global(.fresh) .header {
    box-sizing: border-box;
    height: var(--section-header-height);
    align-items: center;
    gap: 8px;
    margin: 0;
    padding-inline: 12px;
  }
  :global(.fresh) .header-label {
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
  }
  :global(.fresh) .header::after {
    content: "";
    flex: 1 1 0;
    height: 1px;
    background-color: var(--border);
  }
</style>

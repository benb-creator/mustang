<hbox class="attachment">
  <hbox class="icon">
    <FileIcon {ext} localFilePath={$attachment.filename} size={32} />
  </hbox>
  <vbox flex class="right">
    <hbox class="name font-small">
      {attachment.filename}
    </hbox>
    <hbox class="second-line">
      <hbox class="size font-small">
        {$t`${Math.ceil($attachment.size / 1024)} KB`}
      </hbox>
      <hbox flex />
      <hbox class="buttons">
        <Button plain icon={DeleteIcon} iconSize="16px" iconOnly onClick={onDelete} />
        <!--<Button plain icon={ChevronDownIcon} iconSize="16px" iconOnly />-->
      </hbox>
    </hbox>
  </vbox>
</hbox>

<script lang="ts">
  import type { Attachment } from "../../../../logic/Abstract/Attachment";
  import FileIcon from "../../../Files/Thumbnail/FileIcon.svelte";
  import Button from "../../../Shared/Button.svelte";
  import ChevronDownIcon from "lucide-svelte/icons/chevron-down";
  import DeleteIcon from "lucide-svelte/icons/trash-2";
  import { Collection } from "svelte-collections";
  import { t } from "../../../../l10n/l10n";

  export let attachment: Attachment;
  export let attachments: Collection<Attachment>;

  $: ext = attachment.filename.split(".").pop();

  async function onDelete() {
    attachments.remove(attachment);
  }
</script>

<style>
  .attachment {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
    box-shadow: -1px 0px 5px 0.5px rgb(0, 0, 0, 10%);
    border-radius: 5px;
    margin: 4px 6px 4px 12px;
    padding: 4px;
  }
  .icon {
    color: lightgray;
    margin-inline-end: 4px;
  }
  .icon :global(svg) {
    stroke-width: 1px;
  }
  .right {
    margin: 0px 4px;
  }
  .name {
    flex-wrap: wrap;
    font-weight: 500;
    line-height: 1.2;
  }
  .size {
    color: lightgray;
  }
  .buttons {
    align-items: start;
  }
  .buttons :global(svg) {
    color: lightgrey;
  }

  :global(.fresh) .attachment {
    align-items: center;
    max-width: 320px;
    height: 36px;
    box-sizing: border-box;
    margin: 0;
    padding: 0 2px 0 8px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    background-color: var(--l3-bg);
    color: var(--fg-1);
    box-shadow: none;
  }
  :global(.fresh) .icon {
    flex: none;
    margin-inline-end: 8px;
    color: var(--fg-2);
  }
  :global(.fresh) .icon :global(svg) {
    width: 20px;
    height: 20px;
    stroke-width: 1.5px;
  }
  :global(.fresh) .right {
    flex-direction: row;
    align-items: center;
    gap: 8px;
    min-width: 0;
    margin: 0;
  }
  :global(.fresh) .name {
    display: block;
    min-width: 0;
    font-size: var(--text-m);
    line-height: var(--line-m);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.fresh) .second-line {
    flex: none;
    align-items: center;
    gap: 2px;
  }
  :global(.fresh) .second-line > hbox[flex] {
    display: none;
  }
  :global(.fresh) .size {
    font-size: var(--text-s);
    color: var(--fg-2);
    white-space: nowrap;
  }
  :global(.fresh) .buttons {
    align-items: center;
  }
  :global(.fresh) .buttons :global(svg) {
    color: inherit;
  }
</style>

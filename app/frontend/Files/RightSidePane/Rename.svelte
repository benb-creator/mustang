<hbox class="name-container">
  {#if isRenaming}
    <input type="text" class="name-input" bind:value={name}
      autofocus
      on:keydown={event => catchErrors(() => onKeyEnter(event, onRenameSave))}
      />
  {:else}
    <Clickable onDoubleClick={onRenameStart}>
      <hbox class="name">
        {file.name}
      </hbox>
    </Clickable>
  {/if}
  <hbox flex />
  <hbox class="buttons">
    <RoundButton
      onClick={isRenaming ? onRenameSave : onRenameStart}
      icon={isRenaming ? OKIcon : PencilIcon}
      iconSize="16px"
      padding="6px"
      classes="rename plain"
      border={false}
      />
  </hbox>
</hbox>

<script lang="ts">
  import type { FileOrDirectory } from "../../../logic/Files/FileOrDirectory";
  import { File } from "../../../logic/Files/File";
  import { onKeyEnter } from "../../Util/util";
  import Clickable from "../../Shared/Clickable.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import PencilIcon from "lucide-svelte/icons/pencil";
  import OKIcon from "lucide-svelte/icons/check";
  import { catchErrors } from "../../Util/error";

  export let file: FileOrDirectory;

  let name = file.name;
  let isRenaming = false;
  function onRenameStart() {
    if (file instanceof File) {
      name = file.nameWithoutExt;
    } else {
      name = file.name;
    }
    isRenaming = true;
  }
  async function onRenameSave() {
    if (file instanceof File) {
      file.name = name + (file.ext ? "." + file.ext : "");
      file.nameWithoutExt = name;
    } else {
      file.name = name;
    }
    isRenaming = false;
    await file.save();
  }
</script>

<style>
  .name {
    font-size: 120%;
    font-weight: bold;
  }
  input {
    font-size: 120%;
    font-weight: bold;
  }
  .buttons {
    align-items: start;
  }
  :global(.fresh) .name-container {
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  :global(.fresh) .name {
    display: block;
    min-width: 0;
    font-size: var(--text-xl);
    line-height: var(--line-xl);
    font-weight: 600;
    color: var(--fg-1);
    overflow-wrap: anywhere;
  }
  :global(.fresh) .name-input {
    flex: 100 1 0;
    min-width: 0;
    height: var(--control-height);
    font-size: var(--text-l);
    font-weight: 600;
  }
  :global(.fresh) .buttons {
    align-items: center;
  }
</style>

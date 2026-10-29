<vbox>
  <Clickable onClick={onSelect}>
    <hbox class="topic" class:selected={topic == selectedTopic}>
      <hbox class="name">{$topic.name}</hbox>
      <hbox flex />
      <hbox class="buttons">
        <RoundButton
          label={$t`Add sub-topic`}
          icon={PlusIcon}
          onClick={() => isAdding = true}
          iconSize="16px"
          padding="2px"
          border={false}
          classes="plain"
          />
      </hbox>
    </hbox>
  </Clickable>

  <vbox class="children">
    {#each $children.each as child}
      <svelte:self topic={child} bind:selectedTopic />
    {/each}
  </vbox>

  <hbox class="new-child">
    {#if isAdding}
      <!-- svelte-ignore a11y_autofocus -->
      <input type="text" bind:value={newName}
        autofocus on:keydown={event => catchErrors(() => onKeyEnter(event, onAddChild))} />
      <RoundButton
        label={$t`Add sub-topic`}
        icon={PlusIcon}
        onClick={onAddChild}
        iconSize="16px"
        padding="4px"
        disabled={!newName}
        />
    {/if}
  </hbox>
</vbox>

<script lang="ts">
  import { Topic } from "../../../logic/Topic/Topic";
  import { rootTopic } from "../../../logic/Topic/TopicAccounts";
  import Clickable from "../../Shared/Clickable.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import PlusIcon from "lucide-svelte/icons/plus";
  import { onKeyEnter } from "../../Util/util";
  import { catchErrors } from "../../Util/error";
  import { assert } from "../../../logic/util/util";
  import { t } from "../../../l10n/l10n";

  export let topic: Topic;
  /** in/out */
  export let selectedTopic: Topic;

  $: children = topic.children;

  function onSelect() {
    selectedTopic = topic == rootTopic ? null : topic;
  }

  let isAdding = false;
  let newName: string;
  async function onAddChild() {
    assert(newName, "Need name");
    await topic.newChild(newName);
    newName = "";
    isAdding = false;
  }
</script>

<style>
  .topic {
    margin-block: 6px;
    padding-inline: 8px;
    border-radius: 5px;
    border: 1px solid var(--border);
    background-color: var(--bg);
    color: var(--fg);
    max-width: 10em;
  }
  .topic .buttons :global(button) {
    opacity: 60%;
  }
  .children,
  .new-child {
    margin-inline-start: 32px;
  }
  .new-child {
    max-width: 15em;
  }
  .new-child input {
    margin-inline-end: 6px;
  }
  .buttons {
    align-items: center;
  }
  :global(.fresh) .topic {
    position: relative;
    isolation: isolate;
    box-sizing: border-box;
    min-height: var(--nav-row-height);
    max-width: none;
    align-items: center;
    gap: 4px;
    margin: 0;
    padding-inline: 0 2px;
    border: none;
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .topic::before {
    content: "";
    position: absolute;
    z-index: -1;
    inset-block: 0;
    inset-inline: -100vw -12px;
  }
  :global(.fresh) .topic:hover::before {
    background-color: var(--row-hover);
  }
  :global(.fresh) .topic.selected::before {
    border-block: 1px solid var(--border);
    background-color: var(--l3-bg);
  }
  :global(.fresh) .topic.selected .name {
    font-weight: 600;
  }
  :global(.fresh) .topic .name {
    display: block;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.fresh) .topic .buttons :global(.button) {
    opacity: 0;
  }
  :global(.fresh) .topic:hover .buttons :global(.button),
  :global(.fresh) .topic:focus-within .buttons :global(.button) {
    opacity: 1;
  }
  :global(.fresh) .children,
  :global(.fresh) .new-child {
    margin-inline-start: var(--nav-row-indent);
  }
  :global(.fresh) .new-child {
    align-items: center;
    gap: 4px;
  }
  :global(.fresh) .new-child input {
    margin-inline-end: 0;
  }
</style>

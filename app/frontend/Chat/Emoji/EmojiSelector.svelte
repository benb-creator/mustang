<hbox class="emoji-selector" flex>
  <hbox class="selector">
    <Scroll>
      <vbox class="group-selector">
        {#each emojisList as group}
          <RoundButton
            label={group.title}
            onClick={() => onScrollTo(group)}
            border={false} classes="plain"
            padding="0px"
            >
            <hbox class="icon font-large" slot="icon">
              {group.icon}
            </hbox>
          </RoundButton>
        {/each}
      </vbox>
    </Scroll>
  </hbox>
  <Scroll>
    <vbox class="groups">
      {#each emojisList as group}
        <vbox scroll={group.id}>
          <hbox class="title font-small">
            {group.title}
          </hbox>
          <hbox class="emojis">
            {#each group.emojis as entry}
              <RoundButton
                label={entry.name}
                onClick={() => dispatchEvent("select", { emoji: entry.emoji })}
                border={false} classes="plain"
                padding="0px"
                >
                <hbox class="icon font-large" slot="icon">
                  {entry.emoji}
                </hbox>
              </RoundButton>
            {/each}
          </hbox>
        </vbox>
      {/each}
    </vbox>
  </Scroll>
</hbox>

<script lang="ts">
  import emojisJSON from "./emojis.json";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import { createEventDispatcher } from 'svelte';
  const dispatchEvent = createEventDispatcher<{ select: { emoji: string | null, } }>();

  export let searchTerm: string | null;

  $: emojisList = list(searchTerm);

  function list(searchTerm: string) {
    if (!searchTerm) {
      return emojisJSON;
    }
    let term = searchTerm.toLowerCase();
    let list = [];
    for (let group of emojisJSON) {
      let emojis = [];
      for (let emoji of group.emojis) {
        if (emoji.keywords.some(keyword => keyword.includes(term))) {
          emojis.push(emoji);
        }
      }
      if (emojis.length) {
        let filteredGroup = Object.assign({}, group);
        filteredGroup.emojis = emojis;
        list.push(filteredGroup);
      }
    }
    return list;
  }

  function onScrollTo(group: any) {
    let groupE = document.querySelector(`vbox[scroll=${group.id}]`);
    groupE?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start'});
  }
</script>

<style>
  .groups {
    padding: 4px 8px;
  }
  .group-selector .icon {
    font-size: 20px;
  }
  .title {
    opacity: 70%;
    margin-block-end: 2px;
  }
  .emojis {
    flex-wrap: wrap;
    margin-block-end: 8px;
  }
  .selector {
    width: 48px;
  }

  :global(.fresh) .groups {
    padding: 0 8px 8px;
  }
  :global(.fresh) .title {
    margin-block: 8px 4px;
    font-size: var(--text-s);
    font-weight: 600;
    color: var(--fg-2);
    opacity: 1;
  }
  :global(.fresh) .emojis {
    gap: 0;
    margin-block-end: 0;
  }
  :global(.fresh) .selector {
    flex: none;
    width: 40px;
    border-inline-end: 1px solid var(--border-subtle);
  }
  :global(.fresh) .group-selector {
    align-items: center;
    padding-block: 4px;
  }
  :global(.fresh) .group-selector .icon {
    font-size: var(--text-xl);
  }
  :global(.fresh) .emojis .icon {
    font-size: var(--text-2xl);
  }
</style>

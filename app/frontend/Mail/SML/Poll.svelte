<vbox class="poll">
  <fieldset class="options">
    <legend class="question font-normal">{poll.name}</legend>
    {#each ensureArray(poll.options) as option}
      <label class="option">
        <input type="radio" value={option} bind:group={myReaction.object}>
        <vbox>
          <hbox class="title">{option.name}</hbox>
          {#if option.description}
            <hbox class="description">{option.description}</hbox>
          {/if}
        </vbox>
      </label>
    {/each}
  </fieldset>
</vbox>

<script lang="ts">
  import { SMLData } from "../../../logic/Mail/SML/SMLData";
  import type { TSMLSimplePoll, TSMLAction, TSMLThing } from "../../../logic/Mail/SML/TSML";
  import { ensureArray } from "../../../logic/util/util";

  export let sml: SMLData;
  export let myReaction: TSMLAction;

  $: poll = $sml.sml as any as TSMLSimplePoll<TSMLThing>;
</script>

<style>
  .poll {
    align-items: center;
  }
  fieldset {
    border: none;
    margin: 24px 12px 12px 12px;
  }
  legend.question {
    margin-block-end: 4px;
    font-weight: bold;
  }
  label.option {
    display: flex;
    align-items: start;
  }
  input {
    margin-block-start: 5px;
    margin-inline-end: 12px;
  }
  .title {
    font-weight: bold;
  }

  :global(.fresh) .poll {
    align-items: start;
  }
  :global(.fresh) fieldset.options {
    margin: 16px 24px 8px;
    padding: 0;
  }
  :global(.fresh) legend.question {
    margin-block-end: 8px;
    font-size: var(--text-l);
    font-weight: 600;
  }
  :global(.fresh) label.option {
    gap: 8px;
    padding-block: 4px;
  }
  :global(.fresh) .option input {
    margin: 2px 0 0;
  }
  :global(.fresh) .title {
    font-weight: 600;
  }
  :global(.fresh) .description {
    color: var(--fg-2);
  }
</style>

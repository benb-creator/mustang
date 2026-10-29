<vbox class="poll-create" bind:this={pollE}>
  <!--<hbox class="question">
    <hbox class="label">{$t`Question`}</hbox>
    <input type="text" bind:value={poll.name} />
  </hbox>-->
  <hbox class="label answers">{$t`Possible answers`}</hbox>
  {#each poll.options as option}
    <hbox class="option added">
      <input type="radio" name="poll" disabled>
      <vbox>
        <input type="text" class="title" bind:value={option.name}
          on:keydown={(event) => catchErrors(() => onKeyEnter(event, onNewLine))} />
      </vbox>
    </hbox>
  {/each}
  <hbox class="option new">
    <input type="radio" name="poll" disabled>
    <vbox>
      <input type="text" class="title" bind:value={newLine} on:input={() => catchErrors(onNewLine)} />
    </vbox>
  </hbox>
</vbox>

<script lang="ts">
  import { SMLData } from "../../../logic/Mail/SML/SMLData";
  import type { TSMLSimplePoll, TSMLThing } from "../../../logic/Mail/SML/TSML";
  import { onKeyEnter } from "../../Util/util";
  import { catchErrors } from "../../Util/error";
  import { t } from "../../../l10n/l10n";
  import { tick } from "svelte";

  export let sml: SMLData;
  $: poll = $sml.sml as any as TSMLSimplePoll<TSMLThing>;

  function addOption(title?: string) {
    poll.options.push({
      "@type": "Answer",
      name: title,
      description: "",
    } as TSMLThing);
    poll = poll;
  }

  let newLine: string;
  let pollE: HTMLElement;
  async function onNewLine() {
    addOption(newLine);
    newLine = "";
    await tick();
    let textInputs = pollE.querySelectorAll(".option.added .title");
    let newTextInput = textInputs[textInputs.length - 1] as HTMLInputElement;
    newTextInput.focus();
  }
</script>

<style>
  .label {
    white-space: nowrap;
    margin-inline-end: 12px;
    opacity: 70%;
  }
  .question {
    align-items: baseline;
  }
  .question input {
    font-weight: bold;
  }
  .answers {
    margin-block-start: 12px;
    margin-block-end: 6px;
  }
  .option {
    align-items: start;
  }
  input[type=radio] {
    margin-inline-end: 12px;
    margin-block-start: 6px;
  }
  input[type=text] {
    margin-block: 4px;
  }
  .title {
    font-weight: bold;
  }

  :global(.fresh) .poll-create {
    gap: 4px;
  }
  :global(.fresh) .label {
    font-size: var(--text-s);
    font-weight: 600;
    color: var(--fg-2);
    opacity: 1;
  }
  :global(.fresh) .answers {
    margin-block: 0 4px;
  }
  :global(.fresh) .option {
    align-items: center;
  }
  :global(.fresh) .option input[type=radio] {
    margin-block-start: 0;
  }
  :global(.fresh) .option input[type=text] {
    min-width: 20em;
    margin-block: 0;
  }
  :global(.fresh) .title {
    font-weight: 600;
  }
</style>

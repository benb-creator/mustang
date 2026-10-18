<hbox flex class="person" class:selected={isSelected} on:click
  style="--account-color: {addressbook?.color ?? "transparent"};"
  >
    <slot name="icon" />
    <PersonPicture {person} size={pictureSize} />
  <vbox flex class="main">
    <hbox class="first-row">
      <hbox flex class="name {fontClass}">{$person.name}</hbox>
      <slot name="top-right" {person} />
    </hbox>
    <hbox class="second-row">
      <slot name="second-row" {person} />
    </hbox>
  </vbox>
</hbox>

<script lang="ts">
  import type { PersonOrGroup } from "./PersonOrGroup";
  import { appGlobal } from "../../../logic/app";
  import PersonPicture from "./PersonPicture.svelte";

  export let person: PersonOrGroup;
  export let isSelected = false;
  export let pictureSize: number;

  $: fontClass = appGlobal.isMobile ? "font-normal" : "font-small";
  $: addressbook = ($person as any).addressbook;
</script>

<style>
  .person.selected {
    background-color: var(--selected-bg);
    color: var(--selected-fg);
  }
  .person:not(.selected):hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .person {
    align-items: center;
    min-height: 34px;
  }
  .person :global(.avatar),
  .person :global(svg) {
    margin: 4px 10px 4px 16px;
  }

  /* account color bar */
  .person {
    position: relative;
  }
  .person::before {
    position: absolute;
    inset-inline-start: 6px;
    top: 9px;
    bottom: 9px;
    content: "";
    width: 3px;
    background-color: var(--account-color);
    border-radius: 2px;
  }

  .main {
    justify-content: center;
    margin-block-start: 0px;
    padding: 1px 6px 0px 0px;
    max-width: calc(100% - 46px - 2 * 6px); /* HACK Fix long names overdrawing into avatar column */
  }
  :global(.mobile) .main {
    min-height: 44px;
  }
  .first-row {
    height: 1.3em; /* prevent line breaks */
  }
  .name {
    align-items: center;
    white-space: nowrap;
    max-height: 1.3em;
    overflow: hidden;
  }
  .second-row:first-child {
    max-height: 1.3em;
  }
</style>

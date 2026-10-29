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
  .person :global(.avatar),
  .person :global(svg) {
    margin: 2px 14px;
  }

  /* account color bar */
  .person {
    position: relative;
  }
  .person::before {
    position: absolute;
    left: 8px;
    top: 15%;
    content: "";
    height: 70%;
    border-left: 3px solid var(--account-color);
    border-radius: 10px;
  }

  .main {
    justify-content: center;
    margin-block-start: 0px;
    padding: 1px 6px 0px 0px;
    max-width: calc(100% - 42px - 2 * 6px); /* HACK Fix long names overdrawing into avatar column */
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

  :global(.lookout-window) .person {
    align-items: center;
    box-sizing: border-box;
    min-height: 56px;
    border-block-end: 1px solid var(--lo-divider);
  }
  :global(.lookout-window) .person :global(.avatar) {
    flex-shrink: 0;
    margin: 0 12px;
  }
  :global(.lookout-window) .name {
    font-size: 15px;
  }
  :global(.lookout-window) .person.selected {
    color: var(--lo-fg);
  }
  :global(.lookout-window) .person::before {
    display: none;
  }
  :global(.lookout-window) .person.selected::before {
    display: block;
    top: 0;
    left: 0;
    height: 100%;
    border-left: 3px solid var(--lo-accent);
    border-radius: 0;
  }

  :global(.fresh) .person {
    align-items: center;
    gap: 12px;
    box-sizing: border-box;
    min-height: var(--contact-row-height);
    padding-block: 6px;
    padding-inline: 16px 12px;
  }
  :global(.fresh) .person:not(.selected):hover {
    background-color: transparent;
    color: inherit;
  }
  :global(.fresh) .person.selected {
    background-color: var(--sel-inactive-bg);
    color: var(--fg-1);
  }
  :global(.fresh .fast-list:focus-within) .person.selected {
    --fg-1: var(--sel-fg);
    --fg-2: var(--sel-fg-2);
    --fg-3: var(--sel-fg-2);
    --accent-fg: var(--sel-fg);
    background-color: var(--sel-bg);
    color: var(--sel-fg);
  }
  :global(.fresh) .person :global(.avatar),
  :global(.fresh) .person :global(svg) {
    flex: none;
    margin: 0;
  }
  :global(.fresh) .person::before {
    display: none;
    top: 25%;
    left: auto;
    inset-inline-start: 4px;
    height: 50%;
    border-left: none;
    border-inline-start: 3px solid var(--account-color);
    border-radius: 2px;
  }
  :global(.fresh .show-addressbook) .person::before {
    display: block;
  }
  :global(.fresh) .main {
    gap: 2px;
    min-width: 0;
    max-width: none;
    padding: 0;
  }
  :global(.fresh) .first-row {
    align-items: baseline;
    gap: 8px;
    height: auto;
    min-width: 0;
  }
  :global(.fresh) .name {
    display: block;
    min-width: 0;
    max-height: none;
    font-size: var(--text-m);
    line-height: var(--line-m);
    font-weight: 600;
    color: var(--fg-1);
    text-overflow: ellipsis;
  }
  :global(.fresh) .second-row {
    min-width: 0;
    max-height: none;
    font-size: var(--text-s);
    line-height: var(--line-s);
    color: var(--fg-2);
  }
  :global(.fresh) .second-row:empty {
    display: none;
  }
</style>

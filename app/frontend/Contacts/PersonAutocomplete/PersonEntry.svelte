<Clickable onClick={onPopupToggle}>
  <hbox class="person"
    class:selected={popupOpen}
    class:no-pic={!$person.person?.picture}
    title={person.name + "\n" + person.emailAddress}
    bind:this={popupAnchor}>
    <slot name="before-avatar" />
    {#if $person.person?.picture}
      <PersonPicture person={$person.person} size={24} />
    {/if}
    <vbox flex class="right">
      <hbox flex class="name">{$person.name || $person.emailAddress}</hbox>
    </vbox>
    <slot name="after-name" />
  </hbox>
</Clickable>
<Popup bind:popupOpen {popupAnchor} placement="bottom-start" boundaryElSel=".mail-composer-window">
  <PersonPopup personUID={person}
    {onRemovePerson}
    on:close={onPopupClose}
    {disabled}
    >
    <slot name="person-popup-bottom" slot="bottom" personUID={person} />
    <slot name="person-popup-buttons" slot="buttons" personUID={person} />
  </PersonPopup>
</Popup>
<vbox class="context-menu" class:open>
  <slot name="context-menu" {person} />
</vbox>

<script lang="ts">
  import type { PersonUID } from "../../../logic/Abstract/PersonUID";
  import PersonPopup from "./PersonPopup.svelte";
  import PersonPicture from "../Person/PersonPicture.svelte";
  import Popup from "../../Shared/Popup.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import { createEventDispatcher } from 'svelte';
  const dispatchEvent = createEventDispatcher<{ focusNext: void }>();

  export let person: PersonUID;
  export let disabled = false;
  export let onRemovePerson: (person: PersonUID) => void | Promise<void>;

  // Popup
  let popupOpen = false;
  let popupAnchor: HTMLElement;

  function onPopupToggle(event: MouseEvent) {
    popupOpen = !popupOpen;
  }

  function onPopupClose() {
    popupOpen = false;
    dispatchEvent("focusNext");
  }
</script>

<style>
  .person {
    background-color: var(--main-bg);
    color: var(--main-fg);
    border-radius: 100px;
    box-shadow: -1px 0px 5px 0.5px rgb(0, 0, 0, 7%);
    align-items: center;
    padding-inline-end: 12px;
    height: 24px;
  }
  .person:not(.selected):hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .person.selected {
    background-color: var(--selected-bg);
    color: var(--selected-fg);
  }
  .person :global(.avatar) {
    margin: 0px;
    margin-inline-end: 6px;
  }
  .no-pic {
    padding-inline-start: 14px;
  }
  .name {
    align-items: center;
    white-space: nowrap;
  }

  .popup {
    z-index: 100;
  }
  .context-menu:not(.open) {
    display: none;
  }

  :global(.fresh) .person {
    --person-picture-size: 18px;
    gap: 6px;
    height: 24px;
    box-sizing: border-box;
    padding-inline: 3px 8px;
    border-radius: var(--radius-s);
    background-color: var(--fill-subtle);
    color: var(--fg-1);
    box-shadow: none;
    font-size: var(--text-m);
    cursor: pointer;
  }
  :global(.fresh) .person:not(.selected):hover {
    background-color: var(--fill-subtle);
    background-image: linear-gradient(var(--row-hover), var(--row-hover));
    color: var(--fg-1);
  }
  :global(.fresh) .person.selected {
    background-color: var(--accent-tint);
    color: var(--fg-1);
    box-shadow: inset 0 0 0 1px var(--accent-border);
  }
  :global(.fresh) .person :global(.avatar) {
    margin: 0;
  }
  :global(.fresh) .no-pic {
    padding-inline-start: 8px;
  }
</style>

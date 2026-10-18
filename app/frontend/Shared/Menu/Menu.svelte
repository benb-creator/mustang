<Popup
  bind:popupOpen={isMenuOpen}
  popupAnchor={anchor}
  {placement}
  {boundaryElSel}>
  <vbox class="menu"
    on:keydown={onKeyPress}>
    <slot />
  </vbox>
</Popup>

<script lang="ts">
  import Popup from "../Popup.svelte";
  import type { Placement } from "@popperjs/core";
  import { setContext } from "svelte";

  /** in/out */
  export let isMenuOpen: boolean = false;
  /** Under/above which element the popup window should appear.
   * The popup will not cover this element, but be just above/below it.
   * in */
  export let anchor: HTMLElement;
  /** Where the popup should appear in relation to the anchor.
   * above/below ("top"/"bottom") and left/right ("start"/"end")
   * in */
  export let placement: Placement = "bottom-end";
  /**
   * In which area the popup may appear. Much larger than the anchor.
   * Typically the entire page,  or just a part of it.
   * Should be large enough to contain the entire popup window
   * in any situation, e.g. if the anchor is in the middle of this area.
   * The popup window will be entirely within this area, and
   * be cut off larger.
   * Document element selector, e.g. '.mail-composer-window'
   * in */
  export let boundaryElSel: string = "body";

  function onKeyPress(event: KeyboardEvent) {
    if (event.key == "Escape") {
      onMenuClose();
    }
  }

  function onMenuClose() {
    isMenuOpen = false;
  }
  setContext("onMenuClose", onMenuClose);
</script>

<style>
  .menu {
    background-color: var(--popup-bg);
    color: var(--fg);
    padding: 4px;
    min-width: 160px;
    outline: 0px;
    display: block;
    text-decoration: none;
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
    border: 1px solid var(--border);
    border-radius: var(--popup-radius);
  }
</style>

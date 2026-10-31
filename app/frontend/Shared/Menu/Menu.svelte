{#if appGlobal.isMobile}
  {#if isMenuOpen}
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <vbox class="sheet-backdrop" on:click={onMenuClose} use:moveToWindow
      transition:fade={{ duration: 150 }}>
      <vbox class="menu sheet"
        on:click|stopPropagation
        on:keydown={onKeyPress}
        transition:fly={{ y: 400, duration: 220, opacity: 1, easing: cubicOut }}>
        <hbox class="sheet-handle" />
        <slot />
      </vbox>
    </vbox>
  {/if}
{:else}
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
{/if}

<script lang="ts">
  import Popup from "../Popup.svelte";
  import { appGlobal } from "../../../logic/app";
  import { fade, fly } from "svelte/transition";
  import { cubicOut } from "svelte/easing";
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

  /** Mobile: Show the sheet above everything, independent of where the menu button is */
  function moveToWindow(sheetE: HTMLElement) {
    sheetE.closest(".main-window")?.append(sheetE);
    return {
      destroy() {
        // When the page closes, Svelte removes only the DOM of the page, and the sheet is no longer in there
        sheetE.remove();
      },
    };
  }
</script>

<style>
  .menu {
    background-color: var(--bg);
    color: var(--fg);
    padding: 4px 0px;
    outline: 0px;
    display: block;
    text-decoration: none;
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
    border-radius: 4px;
    box-shadow:
      rgba(0, 0, 0, 0.05) 0px 1px 3px,
      rgba(0, 0, 0, 0.05) 0px 20px 25px -5px,
      rgba(0, 0, 0, 0.04) 0px 10px 10px -5px;
  }
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    justify-content: end;
    background-color: rgba(0, 0, 0, 30%);
  }
  .menu.sheet {
    max-height: 80vh;
    overflow-y: auto;
    padding-block: 0 12px;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 15%);
  }
  .sheet-handle {
    align-self: center;
    width: 36px;
    height: 4px;
    margin-block: 8px;
    margin-inline: auto;
    border-radius: 2px;
    background-color: var(--border);
  }
</style>

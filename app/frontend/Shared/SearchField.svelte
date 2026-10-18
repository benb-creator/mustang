<hbox class="search" class:has-search={searchInput}>
  <SearchIcon size="16px" />
  <input type="search"
    bind:value={searchInput}
    on:input={onInput}
    on:keydown={onKeyPress}
    placeholder={placeholder ?? $t`Search`}
    class="font-normal"
    bind:this={inputEl}
    {autofocus}
    spellcheck={false} />
  {#if showX || searchInput && showX === null }
    <RoundButton icon={XIcon} iconSize="16px" padding="2px" border={false}
      onClick={onClear} />
  {/if}
</hbox>

<script lang="ts">
  import RoundButton from "./RoundButton.svelte";
  import SearchIcon from "lucide-svelte/icons/search";
  import XIcon from "lucide-svelte/icons/x";
  import { createEventDispatcher } from "svelte";
  import { t } from "../../l10n/l10n";
  const dispatchEvent = createEventDispatcher<{ input: string, clear: void }>();

  /** out only */
  export let searchTerm: string;
  /** Text to show in the empty search field.
   * Default "Search" */
  export let placeholder: string = null;
  export let autofocus: boolean = false;
  export let showX: boolean | null = null; /** null = only when text entered */

  let searchInput: string;
  $: searchInput = searchTerm;
  function onInput() {
    let searchInputLower = searchInput?.toLowerCase();
    if (searchTerm == searchInputLower) {
      return;
    }
    searchTerm = searchInputLower;
    dispatchEvent("input", searchTerm);
  }
  function onClear() {
    searchTerm = null;
    dispatchEvent("clear");
  }

  $: autofocus && inputEl && focus();
  let inputEl: HTMLInputElement;
  export function focus() {
    inputEl.focus();
  }

  function onKeyPress(event: KeyboardEvent) {
    if (event.key == "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClear();
    }
  }
</script>

<style>
  .search {
    align-items: center;
    border: 1px solid var(--border-strong);
    padding-inline-start: 8px;
    padding-inline-end: 4px;
    border-radius: var(--border-radius);
    background-color: field;
    color: fieldtext;
  }
  .search:has(input:focus) {
    border-color: var(--input-focus);
    box-shadow: 0px 0px 0px 1px var(--input-focus);
  }
  .search.has-search {
    border-color: var(--accent);
  }
  .search :global(svg) {
    color: var(--fg-muted);
  }
  input[type="search"] {
    flex: 1 1 0;
    min-width: 0;
    width: auto;
    height: 28px;
    border: none;
    margin-inline-start: 6px;
    background-color: transparent;
    color: inherit;
    font-size: 14px;
  }
  input[type="search"]:focus {
    border: none;
    box-shadow: none;
  }
  :global(.mobile) input[type="search"] {
    height: 40px;
  }
  input::placeholder {
    color: var(--input-placeholder);
  }
  input::-webkit-search-cancel-button {
    display: none;
  }

  .search :global(.button) {
    background-color: transparent;
  }
</style>

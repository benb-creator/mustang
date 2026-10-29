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
    border: 1px solid var(--border);
    padding-inline-start: 8px;
    padding-inline-end: 4px;
    border-radius: var(--search-field-radius);
    background-color: var(--search-field-bg);
    color: fieldtext;
  }
  .search:has(input:focus) {
    border-color: var(--input-focus);
  }
  .search.has-search {
    background-color: var(--inverted-bg);
    color: var(--inverted-fg);
  }
  .search :global(svg) {
    color: #808080;
  }
  input[type="search"] {
    width: 100%;
    height: 24px;
    border: none;
    margin-inline-start: 4px;
    border-radius: var(--search-field-radius);
    background-color: inherit;
    color: inherit;
  }
  :global(.mobile) input[type="search"] {
    height: 40px;
  }
  input::placeholder {
    color: #808080;
  }
  input::-webkit-search-cancel-button {
    display: none;
  }

  .search :global(.button) {
    background-color: transparent;
  }
  :global(.fresh) .search {
    box-sizing: border-box;
    height: var(--control-height);
    gap: 8px;
    padding-inline: 8px 3px;
    border: 1px solid var(--border-input);
    border-radius: var(--radius-m);
    background-color: var(--input-bg);
    color: var(--fg-1);
    transition: border-color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .search:hover {
    border-color: var(--fg-3);
  }
  :global(.fresh) .search:has(input:focus) {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  :global(.fresh) .search.has-search {
    background-color: var(--input-bg);
    color: var(--fg-1);
  }
  :global(.fresh) .search :global(svg) {
    flex: none;
    color: var(--fg-3);
  }
  :global(.fresh) .search input[type="search"] {
    flex: 1 1 0;
    min-width: 0;
    height: 100%;
    margin: 0;
    padding: 0;
    border: none;
    border-radius: 0;
    outline: none;
    background-color: transparent;
    color: inherit;
    font-size: var(--text-m);
  }
  :global(.fresh) .search input::placeholder {
    color: var(--fg-3);
  }
  :global(.fresh) .search :global(.button.button) {
    flex: none;
    min-width: 22px;
    min-height: 22px;
    border-radius: var(--radius-s);
    color: var(--fg-2);
  }
  :global(.fresh) .search :global(.button svg) {
    color: inherit;
  }
</style>

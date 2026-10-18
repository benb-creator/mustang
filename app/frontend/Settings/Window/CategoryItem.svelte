<Clickable onClick={onSelect}>
  <vbox class="settings-category" class:selected>
    <hbox class="label font-small" class:main={category.isMain}>
      {category.name}
    </hbox>
  </vbox>
</Clickable>
{#if isSectionOpen}
  <SubCategoriesList subCategories={category.subCategories} mainCategory={category} />
  <AccountsList {category} />
{/if}

<script lang="ts">
  import type { SettingsCategory } from "../SettingsCategory";
  import { selectedCategory, selectedAccount } from "./selected";
  import { openSettingsCategory } from "./CategoriesUtils";
  import SubCategoriesList from "./SubCategoriesList.svelte";
  import AccountsList from "./AccountsList.svelte";
  import Clickable from "../../Shared/Clickable.svelte";
  import { appGlobal } from "../../../logic/app";

  /** in */
  export let category: SettingsCategory;

  $: selected = category == $selectedCategory;
  $: isSectionOpen = selected || category.subCategories.contains($selectedCategory) || category.accounts.contains($selectedAccount);

  function onSelect() {
    if (appGlobal.isMobile && (category.subCategories.hasItems || category.accounts.hasItems)) {
      isSectionOpen = !isSectionOpen;
    } else {
      openSettingsCategory(category);
    }
  }
</script>

<style>
  .settings-category {
    position: relative;
    align-items: start;
    justify-content: center;
    min-height: 32px;
    box-sizing: border-box;
    padding-inline-start: 18px;
  }
  .settings-category:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .selected {
    background-color: var(--nav-selected-bg);
    color: var(--nav-selected-fg);
  }
  .selected::before {
    content: "";
    position: absolute;
    inset-inline-start: 0px;
    top: 5px;
    bottom: 5px;
    width: 3px;
    border-radius: 2px;
    background-color: var(--accent);
  }
  .label {
    white-space: nowrap;
    overflow: hidden;
    margin-inline-start: 4px;
    margin-inline-end: 4px;
  }
  .label.main {
    font-weight: 600;
  }
</style>

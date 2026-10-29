<AccountItem {account} {category}>
  <NavRow slot="row" let:itemSelected let:onSelect
    label={$account.name}
    indent={1}
    selected={itemSelected}
    nextLevel="l3"
    on:click={() => catchErrors(onSelect)}
    >
    <hbox slot="icon" class="swatch" style:background-color={$account.color} />
  </NavRow>
  <svelte:fragment slot="children" let:subCategories>
    <SubCategoriesList {subCategories} mainCategory={category} let:category={subCategory}>
      <CategoryItem category={subCategory} />
    </SubCategoriesList>
  </svelte:fragment>
</AccountItem>

<script lang="ts">
  import type { Account } from "../../../logic/Abstract/Account";
  import type { SettingsCategory } from "../../../frontend/Settings/SettingsCategory";
  import AccountItem from "../../../frontend/Settings/Window/AccountItem.svelte";
  import SubCategoriesList from "../../../frontend/Settings/Window/SubCategoriesList.svelte";
  import CategoryItem from "./CategoryItem.svelte";
  import NavRow from "../../Shared/NavRow.svelte";
  import { catchErrors } from "../../../frontend/Util/error";

  /** in */
  export let account: Account;
  /** in */
  export let category: SettingsCategory;
</script>

<style>
  .swatch {
    flex: none;
    width: 10px;
    height: 10px;
    margin: 3px;
    border-radius: 2px;
  }
</style>

<CategoryItem {category}>
  <NavRow slot="row" let:selected let:isSectionOpen let:onSelect
    label={category.name}
    main={category.isMain}
    indent={depth}
    expandable={category.isMain ? hasContent : false}
    expanded={isSectionOpen}
    expanderToggles={false}
    {selected}
    nextLevel="l3"
    on:click={() => catchErrors(onSelect)}
    />
  <svelte:fragment slot="children">
    <SubCategoriesList subCategories={category.subCategories} mainCategory={category} let:category={subCategory}>
      <svelte:self category={subCategory} />
    </SubCategoriesList>
    <AccountsList {category} />
  </svelte:fragment>
</CategoryItem>

<script lang="ts">
  import { AccountSettingsCategory, type SettingsCategory } from "../../../frontend/Settings/SettingsCategory";
  import CategoryItem from "../../../frontend/Settings/Window/CategoryItem.svelte";
  import SubCategoriesList from "../../../frontend/Settings/Window/SubCategoriesList.svelte";
  import AccountsList from "./AccountsList.svelte";
  import NavRow from "../../Shared/NavRow.svelte";
  import { catchErrors } from "../../../frontend/Util/error";

  /** in */
  export let category: SettingsCategory;

  $: hasContent = category.subCategories.hasItems || category.accounts.hasItems || !!category.newAccountURL;
  $: depth = category.isMain ? 0 : category instanceof AccountSettingsCategory ? 2 : 1;
</script>

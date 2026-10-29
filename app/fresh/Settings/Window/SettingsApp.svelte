<vbox flex class="settings-app">
  <SettingsApp leftMinWidth={160} rightMinWidth={320}>
    <SettingsCategoriesPane slot="categories" let:categories {categories} />
    <MainContent slot="page" let:onClose category={$selectedCategory}>
      <Button
        slot="actions"
        label={$t`Close settings`}
        icon={CloseIcon}
        iconSize="16px"
        iconOnly
        plain
        onClick={onClose}
        />
    </MainContent>
  </SettingsApp>
</vbox>

<script lang="ts">
  import { selectedCategory } from "../../../frontend/Settings/Window/selected";
  import SettingsApp from "../../../frontend/Settings/Window/SettingsApp.svelte";
  import SettingsCategoriesPane from "./CategoriesPane.svelte";
  import MainContent from "./MainContent.svelte";
  import Button from "../../../frontend/Shared/Button.svelte";
  import CloseIcon from "lucide-svelte/icons/x";
  import { t } from "../../../l10n/l10n";
</script>

<style>
  .settings-app {
    min-width: 0;
    min-height: 0;
    border-block-start: 1px solid var(--border);
    background-color: var(--l3-bg);
  }
</style>

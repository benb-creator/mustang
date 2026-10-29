<hbox class="theme buttons">
  <Button
    label={$t`System`}
    icon={SystemIcon}
    iconSize="16px"
    plain
    onClick={() => switchTo('system')}
    selected={theme == "system"}
    />
  <Button
    label={$t`Light`}
    icon={LightIcon}
    iconSize="16px"
    plain
    onClick={() => switchTo('light')}
    selected={theme == "light"}
    />
  <Button
    label={$t`Dark`}
    icon={DarkIcon}
    classes="vertical"
    iconSize="16px"
    plain
    onClick={() => switchTo('dark')}
    selected={theme == "dark"}
    />
</hbox>

<script lang="ts">
  import { getLocalStorage } from "../../Util/LocalStorage";
  import Button from "../../Shared/Button.svelte";
  import DarkIcon from "lucide-svelte/icons/moon";
  import LightIcon from "lucide-svelte/icons/sun";
  import SystemIcon from "lucide-svelte/icons/app-window";
  import { t } from "../../../l10n/l10n";

  let themeSetting = getLocalStorage("appearance.theme", "system");
  let colorsSetting = getLocalStorage("appearance.colors", {});
  $: theme = $themeSetting.value;

  function switchTo(newTheme: "system" | "light" | "dark") {
    themeSetting.value = newTheme;
    colorsSetting.value = {};
  }
</script>

<style>
  .buttons :global(button) {
    padding: 8px;
    margin-inline-end: 12px;
  }
  :global(.fresh) .theme.buttons {
    flex: none;
    align-self: start;
    align-items: stretch;
    box-sizing: border-box;
    height: 28px;
    border: 1px solid var(--border-control);
    border-radius: var(--radius-m);
    overflow: hidden;
  }
  :global(.fresh) .theme.buttons :global(.button.button) {
    min-height: 0;
    margin: 0;
    padding: 0 10px;
    border: none;
    border-inline-start: 1px solid var(--border-control);
    border-radius: 0;
    background-color: transparent;
    background-image: none;
    color: var(--fg-2);
    font-weight: 500;
  }
  :global(.fresh) .theme.buttons :global(.button.button:first-child) {
    border-inline-start: none;
  }
  :global(.fresh) .theme.buttons :global(.button.button:hover:not(.selected)) {
    background-color: var(--row-hover);
    color: var(--fg-1);
  }
  :global(.fresh) .theme.buttons :global(.button.button.selected) {
    background-color: var(--ink);
    color: var(--ink-fg);
  }
  :global(.fresh) .theme.buttons :global(.button.button.selected + .button) {
    border-inline-start-color: var(--ink);
  }
  :global(.fresh) .theme.buttons :global(.button.button:focus-visible) {
    outline-offset: -2px;
  }
  :global(.fresh) .theme.buttons :global(svg) {
    width: 16px;
    height: 16px;
    stroke-width: 1.75px;
  }
</style>

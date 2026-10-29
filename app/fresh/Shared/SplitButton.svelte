<hbox class="split-button" class:primary bind:this={anchorE}>
  <Button
    {label}
    {icon}
    {iconSize}
    {disabled}
    {tooltip}
    {shortCutInfo}
    {onClick}
    {errorCallback}
    classes="main {primary ? "primary" : "secondary"} {classes}"
    />
  <Button
    label={menuLabel ?? $t`More actions`}
    icon={ChevronIcon}
    iconOnly
    {disabled}
    onClick={onMenuToggle}
    classes="chevron {primary ? "primary" : "secondary"}"
    />
</hbox>
<Menu bind:isMenuOpen anchor={anchorE} {placement} {boundaryElSel}>
  <slot />
</Menu>

<script lang="ts">
  import Button from "../../frontend/Shared/Button.svelte";
  import Menu from "../../frontend/Shared/Menu/Menu.svelte";
  import ChevronIcon from "lucide-svelte/icons/chevron-down";
  import { showError } from "../../frontend/Util/error";
  import type { Placement } from "@popperjs/core";
  import { t } from "../../l10n/l10n";

  export let label: string;
  export let icon: ConstructorOfATypedSvelteComponent | string = null;
  export let iconSize = "16px";
  /** The pane's main action: filled with the accent colour */
  export let primary = false;
  export let classes = "";
  export let disabled: boolean | string = false;
  export let tooltip: string = null;
  export let shortCutInfo: string = null;
  export let onClick: (event: Event) => void;
  export let errorCallback = showError;
  /** Tooltip of the menu part */
  export let menuLabel: string = null;
  /** in/out */
  export let isMenuOpen = false;
  export let placement: Placement = "bottom-end";
  export let boundaryElSel = "body";

  let anchorE: HTMLElement;
  function onMenuToggle() {
    isMenuOpen = !isMenuOpen;
  }
</script>

<style>
  .split-button {
    flex: none;
    align-items: stretch;
  }
  .split-button :global(.button.main) {
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }
  .split-button :global(.button.chevron) {
    width: 26px;
    min-width: 26px;
    padding: 0;
    margin-inline-start: -1px;
    border-start-start-radius: 0;
    border-end-start-radius: 0;
  }
  .split-button.primary :global(.button.chevron) {
    margin-inline-start: 0;
    border-inline-start-color: color-mix(in srgb, var(--fg-on-accent) 35%, transparent);
  }
</style>

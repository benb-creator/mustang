<vbox class="group {classes}">
  <hbox class="header">
    <slot name="icon" />
    <h3>{headerName}</h3>
    <hbox flex class="actions">
      <slot name="buttons-top-right" />
      {#if addFunc && !appGlobal.isMobile}
        <Button
          onClick={addFunc}
          label={addLabel}
          icon={AddIcon}
          iconOnly plain classes="add top" />
      {/if}
    </hbox>
  </hbox>
  <vbox class="content" flex>
    <slot name="content" />

    {#if addFunc && appGlobal.isMobile && isEditing}
      <hbox class="add-row">
        <Button
          onClick={addFunc}
          label={addLabel}
          plain classes="add text" />
        <RoundButton
          onClick={addFunc}
          label={addLabel}
          icon={AddCircleIcon}
          border={false}
          iconSize="24px" classes="plain add bottom" />
      </hbox>
    {/if}
  </vbox>
</vbox>

<script lang="ts">
  import { appGlobal } from "../../../logic/app";
  import Button from "../../Shared/Button.svelte";
  import RoundButton from "../../Shared/RoundButton.svelte";
  import AddIcon from "lucide-svelte/icons/plus";
  import AddCircleIcon from "lucide-svelte/icons/circle-plus";
  import { t } from "../../../l10n/l10n";

  export let classes = "";
  export let headerName: string;

  export let isEditing = false;
  export let addFunc: () => void = null;
  export let addLabel: string = $t`Add`;
</script>

<style>
  .group {
    margin: 5px;
  }
  .header {
    align-items: center;
    padding: 8px 8px 6px 8px;
  }
  .header h3 {
    font-weight: normal;
  }
  h3 {
    margin-inline-start: 10px;
    margin-block-start: 0px;
    margin-block-end: 0px;
    vertical-align: middle;
    font-size: 14px;
  }
  :global(.mobile) h3 {
    font-size: 16px;
    font-weight: 500;
  }
  .actions {
    justify-content: end;
  }
  :global(.group:not(:hover)) .actions {
    visibility: hidden;
  }
  .content {
    background-color: var(--main-bg);
    color: var(--main-fg);
    padding: 8px 16px 10px 20px;
    border-radius: 5px;
  }
  :global(.mobile) .group {
    border: none;
  }
  :global(.mobile) .header {
    background-color: transparent;
  }
  :global(.mobile) .content {
    border-radius: 12px;
    border: 1px solid var(--border);
  }
  .group :global(button.add.top) {
    color: grey;
  }
  .group :global(button.add.text) {
    color: grey;
    font-size: 16px;
    flex: 1 0 0;
  }
  .group :global(button.add.bottom svg) {
    fill: var(--selected-bg);
    color: var(--selected-fg);
  }
  :global(.ios) .group :global(button.add.bottom svg) {
    fill: green;
    color: white;
  }

  :global(.fresh) .group {
    margin: 0 0 12px;
  }
  :global(.fresh) .header {
    gap: 8px;
    box-sizing: border-box;
    min-height: var(--section-header-height);
    padding: 0 24px;
    color: var(--fg-2);
  }
  :global(.fresh) .header::after {
    content: "";
    order: 1;
    flex: 1 0 8px;
    height: 1px;
    background-color: var(--border-subtle);
  }
  :global(.fresh) .header :global(svg) {
    flex: none;
    width: 16px;
    height: 16px;
  }
  :global(.fresh) .header :global(svg path) {
    stroke: currentColor;
  }
  :global(.fresh) .header h3 {
    margin: 0;
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 600;
    color: var(--fg-2);
    white-space: nowrap;
  }
  :global(.fresh) .actions {
    order: 2;
    flex: none;
    align-items: center;
    gap: 2px;
  }
  :global(.fresh) .actions:empty {
    display: none;
  }
  :global(.fresh) .group.person > .header {
    display: none;
  }
  :global(.fresh) .content {
    padding: 4px 24px;
    border-radius: 0;
    background-color: transparent;
    color: inherit;
  }
  :global(.fresh) .group.person > .content {
    padding: 0;
  }
  :global(.fresh) .group :global(button.add.top) {
    color: var(--fg-2);
  }
</style>

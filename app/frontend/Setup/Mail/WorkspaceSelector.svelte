<vbox class="workspace-selector">
  <hbox class="hint font-smallest">{$t`Workspaces allow you to organize yourself. You can change this at any time, by going to Settings in the title bar.`}</hbox>
  <vbox class="workspaces-box" class:horizontal>
    <vbox class="workspaces">
      {#each $workspaces.each as workspace}
        <label class="workspace"
          style="background-color: {workspace.color}"
          >
          <input type="radio"
            checked={workspace == selectedWorkspace}
            value={workspace}
            bind:group={selectedWorkspace}
            />
          {workspace.name}
        </label>
      {/each}
    </vbox>
  </vbox>
</vbox>

<script lang="ts">
  import type { Workspace } from "../../../logic/Abstract/Workspace";
  import { appGlobal } from "../../../logic/app";
  import { t } from "../../../l10n/l10n";

  export let selectedWorkspace: Workspace = appGlobal.workspaces.last;
  export let horizontal = false;

  let workspaces = appGlobal.workspaces;

  function onChange(newWorkspace: Workspace, event: Event) {
    selectedWorkspace = newWorkspace;
    event.stopPropagation();
  }
</script>

<style>
  .hint {
    opacity: 70%;
  }
  .workspaces-box {
    margin-inline-end: 32px;
    padding-block-start: 4px;
    margin-block-start: 12px;
  }
  .workspaces-box:not(.horizontal) {
    align-items: center;
  }
  .workspaces-box.horizontal .workspaces {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .workspace {
    padding: 6px 20px 6px 12px;
    margin: 2px;
  }
  .name {
    margin-inline-start: 8px;
    color: black;
  }
  :global(.fresh) .hint {
    opacity: 1;
    color: var(--fg-2);
    font-size: var(--text-s);
    line-height: var(--line-s);
  }
  :global(.fresh) .workspaces-box {
    margin: 12px 0 0;
    padding: 0;
  }
  :global(.fresh) .workspaces {
    gap: 8px;
  }
  :global(.fresh) .workspace {
    display: flex;
    align-items: center;
    gap: 8px;
    box-sizing: border-box;
    min-height: var(--control-height);
    margin: 0;
    padding: 0 12px 0 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    background-image: linear-gradient(to right, transparent 0 4px, color-mix(in srgb, var(--l3-bg) 82%, transparent) 4px);
    color: var(--fg-1);
    cursor: pointer;
  }
  :global(.fresh[dir="rtl"]) .workspace {
    background-image: linear-gradient(to left, transparent 0 4px, color-mix(in srgb, var(--l3-bg) 82%, transparent) 4px);
  }
  :global(.fresh) .workspace:has(input:checked) {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  :global(.fresh) .workspace input {
    margin: 0;
  }
</style>

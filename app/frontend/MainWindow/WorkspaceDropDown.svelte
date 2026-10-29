<vbox class="workspace-selector">
  {#each [null, ...appGlobal.workspaces.each] as workspace}
    <Clickable onClick={event => onWorkspaceSelected(workspace, event)}>
      <hbox class="workspace"
        style="--workspace-color: {workspace?.color ?? "black"}"
        class:selected={workspace == $selectedWorkspace}
        >
        <!--
        <input type="radio"
          checked={workspace == $selectedWorkspace}
          value={workspace}
          name="workspace"
          on:input={event => onWorkspaceSelected(workspace, event)}
          />
        -->
        <!--<Icon data={workspace?.icon} />-->
        <hbox class="button" />
        <label for="workspace" class="name">{workspace?.name ?? "All"}</label>
      </hbox>

    </Clickable>
  {/each}
</vbox>

<script lang="ts">
  import { Workspace } from "../../logic/Abstract/Workspace";
  import { selectedWorkspace } from "./Selected";
  import { appGlobal } from "../../logic/app";
  import Clickable from "../Shared/Clickable.svelte";

  export let open: boolean;

  function onWorkspaceSelected(workspace: Workspace, event: Event) {
    open = false;
    $selectedWorkspace = workspace;
  }
</script>

<style>
  .workspace-selector {
    margin-block-start: -4px;
    padding: 12px 16px 16px 16px;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
    background-color: var(--appbar-bg);
    color: var(--appbar-fg);
  }
  .workspace {
    padding: 0px 8px;
  }
  /*.workspace {
    background-color: var(--workspace-color);
    color: lch(from var(--workspace-color) calc((49.44 - l) * infinity) 0 0);
  }*/
  .workspace label {
    margin-inline-start: 12px;
  }
  .workspace .button {
    background-color: var(--workspace-color);
    margin: 3px 0px;
    min-width: 18px;
    min-height: 18px;
    border-radius: 18px;
    align-self: center;
  }
  .workspace:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  :global(.fresh) .workspace-selector {
    min-width: 200px;
    margin: 0;
    padding: var(--space-1);
    border-radius: 0;
    background-color: transparent;
    color: var(--fg-1);
  }
  :global(.fresh) .workspace {
    height: var(--menu-item-height);
    align-items: center;
    padding: 0 var(--space-3) 0 var(--space-2);
    border-radius: var(--radius-s);
    font-size: var(--text-m);
    cursor: pointer;
  }
  :global(.fresh) .workspace:hover {
    background-color: var(--row-press);
    color: var(--fg-1);
  }
  :global(.fresh) .workspace.selected {
    font-weight: 600;
  }
  :global(.fresh) .workspace label {
    margin-inline-start: var(--space-2);
    cursor: inherit;
  }
  :global(.fresh) .workspace .button {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--fg-1) 20%, transparent);
    min-width: 10px;
    min-height: 10px;
    margin: 0;
    border-radius: 2px;
  }
</style>

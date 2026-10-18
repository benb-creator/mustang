<vbox class="workspace-selector">
  {#each [null, ...appGlobal.workspaces.each] as workspace}
    <Clickable onClick={event => onWorkspaceSelected(workspace, event)}>
      <hbox class="workspace"
        style="--workspace-color: {workspace?.color ?? "var(--fg-faint)"}"
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
    padding: 4px;
    min-width: 180px;
    border: 1px solid var(--border);
    border-radius: var(--popup-radius);
    background-color: var(--popup-bg);
    color: var(--fg);
  }
  .workspace {
    align-items: center;
    min-height: 32px;
    padding: 0px 10px;
    border-radius: var(--border-radius);
  }
  /*.workspace {
    background-color: var(--workspace-color);
    color: lch(from var(--workspace-color) calc((49.44 - l) * infinity) 0 0);
  }*/
  .workspace label {
    margin-inline-start: 10px;
  }
  .workspace .button {
    background-color: var(--workspace-color);
    min-width: 10px;
    min-height: 10px;
    border-radius: 10px;
    align-self: center;
  }
  .workspace:hover {
    background-color: var(--hover-bg);
    color: var(--hover-fg);
  }
  .workspace.selected {
    font-weight: 600;
  }
</style>

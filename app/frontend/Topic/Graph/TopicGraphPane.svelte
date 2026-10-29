<vbox class="topic-graph-pane" flex>
  {#if view == "graph"}
    <TopicGraph bind:selectedTopic />
  {:else}
    <Scroll>
      <vbox class="tree-branch">
        <TopicTreeBranch topic={rootTopic} bind:selectedTopic />
      </vbox>
    </Scroll>
  {/if}
  <hbox class="switcher">
    <IslandSwitcher>
      <Button
        label={$t`Graph`}
        onClick={() => switchTo("graph")}
        selected={view == "graph"}
        />
      <Button
        label={$t`Table of contents`}
        onClick={() => switchTo("toc")}
        selected={view == "toc"}
        />
    </IslandSwitcher>
  </hbox>
</vbox>

<script lang="ts">
  import { rootTopic } from "../../../logic/Topic/TopicAccounts";
  import { getLocalStorage } from "../../Util/LocalStorage";
  import IslandSwitcher from "../../Shared/IslandSwitcher.svelte";
  import Button from "../../Shared/Button.svelte";
  import Scroll from "../../Shared/Scroll.svelte";
  import TopicGraph from "./TopicGraph.svelte";
  import TopicTreeBranch from "./TopicTreeBranch.svelte";
  import { t } from "../../../l10n/l10n";

  /** in/out */
  export let selectedTopic = rootTopic;

  let viewSetting = getLocalStorage("topic.graphPane.view", "toc");
  $: view = $viewSetting.value;

  function switchTo(newView: string) {
    viewSetting.value = newView;
  }
</script>

<style>
  .topic-graph-pane {
    background-color: var(--leftbar-bg);
    color: var(--leftbar-fg);
  }
  .tree-branch {
    padding: 6px 24px 6px 12px;
  }
  .switcher {
    margin: 6px 8px;
  }
  :global(.fresh) .topic-graph-pane {
    min-width: 0;
    background-color: var(--l1-bg);
    color: var(--l1-fg);
    box-shadow: inset -1px 0 0 var(--border);
  }
  :global(.fresh[dir="rtl"]) .topic-graph-pane {
    box-shadow: inset 1px 0 0 var(--border);
  }
  :global(.fresh) .tree-branch {
    padding: 12px;
  }
  :global(.fresh) .switcher {
    flex: none;
    margin: 0;
    padding: 8px 12px;
    border-block-start: 1px solid var(--border);
  }
  :global(.fresh) .switcher :global(.button .label) {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.fresh) .switcher :global(.button:first-child) {
    flex-shrink: 0;
  }
</style>

<vbox class="topic-app" flex>
  <Splitter {initialRightRatio} leftMinWidth={100} rightMinWidth={500} hasRight={!!selectedTopic}>
    <TopicGraph bind:selectedTopic slot="left" />
    <TopicPage bind:topic={selectedTopic} slot="right" />
  </Splitter>
</vbox>

<script lang="ts">
  import { Topic } from "../../logic/Topic/Topic";
  import TopicGraph from "./Graph/TopicGraphPane.svelte";
  import TopicPage from "./Page/TopicPage.svelte";
  import Splitter from "../Shared/Splitter.svelte";

  export let initialRightRatio = 2;

  let selectedTopic: Topic;
</script>

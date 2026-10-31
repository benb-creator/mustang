<vbox flex class="message-list-pane">
  <FolderHeader folder={selectedFolder} {searchMessages} />
  <vbox flex class="pull-area"
    on:touchstart={onPullStart}
    on:touchmove|nonpassive={onPullMove}
    on:touchend={() => catchErrors(onPullEnd)}
    on:touchcancel={onPullCancel}
    >
    <FetchingM folder={selectedFolder} pullProgress={pullY / kPullDistance} height={kRefreshHeight} bind:this={fetching} />
    <vbox flex class="pull-content" class:animate style:transform={pullY ? `translateY(${pullY}px)` : null}>
      <VerticalMessageList {messages} bind:selectedMessage bind:selectedMessages
        on:click={() => catchErrors(goToMessage)} />
    </vbox>
  </vbox>
  {#if selectedFolder && !(selectedFolder instanceof SavedSearchFolder) && availableTags.hasItems}
    <TagsList folder={selectedFolder} bind:searchMessages showStaticLabel={false} />
  {/if}
  <FolderFooter folder={selectedFolder} bind:searchMessages showGetMail={false} />
  <MessageListBarM folder={selectedFolder} />
</vbox>

<script lang="ts">
  import type { Folder } from "../../../logic/Mail/Folder";
  import type { EMail } from "../../../logic/Mail/EMail";
  import { availableTags } from "../../../logic/Abstract/Tag";
  import { SavedSearchFolder } from "../../../logic/Mail/Virtual/SavedSearchFolder";
  import { openEMailMessage } from "../open";
  import VerticalMessageList from "./VerticalMessageList.svelte";
  import FolderHeader from "../LeftPane/FolderHeader.svelte";
  import FolderFooter from "../LeftPane/FolderFooter.svelte";
  import TagsList from "../LeftPane/TagsList.svelte";
  import MessageListBarM from "./MessageListBarM.svelte";
  import FetchingM from "./FetchingM.svelte";
  import { catchErrors } from "../../Util/error";
  import { sleep, assert } from "../../../logic/util/util";
  import type { ArrayColl } from 'svelte-collections';

  export let messages: ArrayColl<EMail>; /** in */
  export let searchMessages: ArrayColl<EMail> | null; /** out */
  export let selectedFolder: Folder; /** in */
  export let selectedMessage: EMail; /** in/out */
  export let selectedMessages: ArrayColl<EMail>; /** in/out */

  async function goToMessage() {
    await sleep(0); // wait for `<VerticalMessageList>` to set `selectedMessage`
    assert(selectedMessage, "Need message");
    await openEMailMessage(selectedMessage);
  }

  // Pull down to check mail
  let fetching: FetchingM;
  /** How far the list moved down, in px */
  let pullY = 0;
  /** Slide to the new `pullY`, instead of following the finger */
  let animate = false;
  let isRefreshing = false;
  let pullState: "idle" | "deciding" | "pulling" = "idle";
  let pullStartX = 0;
  let pullStartY = 0;
  /** in px */
  const kPullDistance = 72;
  const kRefreshHeight = 56;

  function onPullStart(event: TouchEvent) {
    let listE = (event.currentTarget as HTMLElement).querySelector(".fast-list");
    if (isRefreshing || event.touches.length != 1 || listE?.scrollTop > 0) {
      pullState = "idle";
      return;
    }
    pullStartX = event.touches[0].clientX;
    pullStartY = event.touches[0].clientY;
    pullState = "deciding";
  }

  function onPullMove(event: TouchEvent) {
    if (pullState == "idle" || event.defaultPrevented) {
      return;
    }
    let deltaX = event.touches[0].clientX - pullStartX;
    let deltaY = event.touches[0].clientY - pullStartY;
    if (pullState == "deciding") {
      if (Math.abs(deltaX) < 8 && Math.abs(deltaY) < 8) {
        return;
      }
      if (deltaY <= 0 || Math.abs(deltaX) > deltaY) {
        pullState = "idle";
        return;
      }
      pullState = "pulling";
      animate = false;
    }
    event.preventDefault();
    pullY = Math.max(0, Math.min(deltaY * 0.5, kPullDistance * 1.6));
  }

  async function onPullEnd() {
    if (pullState != "pulling") {
      pullState = "idle";
      return;
    }
    pullState = "idle";
    animate = true;
    if (pullY < kPullDistance) {
      pullY = 0;
      return;
    }
    pullY = kRefreshHeight;
    isRefreshing = true;
    try {
      await fetching.onCheckMail();
    } finally {
      isRefreshing = false;
      pullY = 0;
    }
  }

  function onPullCancel() {
    pullState = "idle";
    if (!isRefreshing) {
      animate = true;
      pullY = 0;
    }
  }
</script>

<style>
  .message-list-pane {
    background-color: var(--main-bg);
    color: var(--main-fg);
  }
  .message-list-pane {
    box-shadow: 1px 0px 6px 0px rgba(0, 0, 0, 8%); /* Also on MessageList */
    z-index: 2;
  }
  .pull-area {
    position: relative;
    overflow: hidden;
  }
  .pull-content {
    position: relative;
    z-index: 1;
    background-color: var(--main-bg);
  }
  .pull-content.animate {
    transition: transform 220ms cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  @media (prefers-reduced-motion: reduce) {
    .pull-content.animate {
      transition: none;
    }
  }
</style>

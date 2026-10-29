<Clickable onClick={onOpen}>
  <vbox class="email" flex
    title={message.subject + "\n\n" + (message.text?.substring(0, 300) ?? "")}>
    <div class="subject">
      {message.subject}
    </div>
    <div class="body">
      {message.text?.substring(0, 240) ?? ""}
    </div>
  </vbox>
</Clickable>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { openEMailMessage } from "../../Mail/open";
  import { SearchView } from "../../Mail/LeftPane/SearchSwitcher.svelte";
  import Clickable from "../../Shared/Clickable.svelte";

  export let message: EMail;

  async function onOpen() {
    await openEMailMessage(message, SearchView.Person);
  }
</script>

<style>
  .subject,
  .body {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .subject {
    max-height: 1.4em;
    margin-block-start: -1px;
    margin-block-end: 3px;
    font-weight: bold;
  }
  .body {
    max-height: 2.4em;
    line-height: 1.2em;
    font-weight: 300;
  }
  :global(.fresh) .subject {
    max-height: var(--line-m);
    margin: 0 0 2px;
    font-size: var(--text-m);
    line-height: var(--line-m);
    font-weight: 600;
    color: var(--fg-1);
    white-space: nowrap;
  }
  :global(.fresh) .body {
    max-height: calc(2 * var(--line-s));
    font-size: var(--text-s);
    line-height: var(--line-s);
    font-weight: 400;
    color: var(--fg-2);
  }
</style>

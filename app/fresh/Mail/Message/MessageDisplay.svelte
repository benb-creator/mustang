<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<vbox flex class="message-display"
  on:keydown={event => catchErrors(() => onKeyOnList(event))}
  tabindex={0}
  >
  <MessageHeader bind:message />
  <vbox class="attachments-sml">
    <MessageAttachments attachments={message.attachments} />
    <SMLDisplayKinds {message} sml={message.sml} />
  </vbox>
  <vbox class="body" flex>
    <MessageBody {message} />
  </vbox>
</vbox>

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import { onKeyOnList } from "../../../frontend/Mail/Message/MessageKeyboard";
  import MessageHeader from "./MessageHeader.svelte";
  import MessageAttachments from "../../../frontend/Mail/Message/AttachmentsUI.svelte";
  import MessageBody from "../../../frontend/Mail/Message/MessageBody.svelte";
  import SMLDisplayKinds from "../../../frontend/Mail/SML/SMLDisplayKinds.svelte";
  import { catchErrors } from "../../../frontend/Util/error";

  export let message: EMail;
</script>

<style>
  .message-display {
    min-width: 0;
    background-color: var(--l3-bg);
    color: var(--l3-fg);
    container-type: inline-size;
  }
  .message-display:focus-visible {
    outline-offset: -2px;
  }
  .attachments-sml {
    flex: none;
    padding-inline: 20px;
  }
  .attachments-sml:empty {
    display: none;
  }
  .body {
    min-height: 0;
  }
</style>

<hbox class="left" />
<LogTime {message} {previousMessage} />
<LogIconByType {message} {previousMessage} />
<vbox class="content">
  <LogContentByType {message} />
</vbox>

<script lang="ts">
  import type { LogEntry } from "../../../logic/Contacts/History/History";
  import type { Person } from "../../../logic/Abstract/Person";
  import LogTime from "./LogTime.svelte";
  import LogIconByType from "./LogIconByType.svelte";
  import LogContentByType from "./LogContentByType.svelte";

  export let message: LogEntry;
  export let previousMessage: LogEntry;
  export let person: Person;
</script>

<style>
  .content {
    padding: 4px 12px;
    height: 56px;
  }
  .left {
    padding-inline-start: 12px;
  }
  :global(.fresh) .content {
    justify-content: center;
    box-sizing: border-box;
    min-width: 0;
    padding: 4px 24px 4px 8px;
  }
  :global(.fresh) .left {
    padding-inline-start: 24px;
  }
</style>

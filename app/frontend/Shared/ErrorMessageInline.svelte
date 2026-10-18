{#if ex}
  <hbox class="error">
    <hbox class="icon">
      <ErrorIcon />
    </hbox>
    <div class="value">
      {console.error(ex), logError(ex), ""}
      {ex.message ?? ex + ""}
    </div>
  </hbox>
{/if}

<script lang="ts">
  import { logError } from "../Util/error";
  import ErrorIcon from "lucide-svelte/icons/triangle-alert";

  export let ex: Error = null;

  export function showError(error: Error) {
    ex = error;
  }
  export function clearError() {
    ex = null;
  }
</script>

<style>
  .error {
    background-color: var(--offset-bg);
    color: var(--fg);
    border: 1px solid var(--border);
    border-inline-start: 3px solid var(--danger-fg);
    border-radius: var(--border-radius);
    padding: 8px 12px;
    margin: 8px;
  }
  .icon {
    margin-inline-end: 12px;
    color: var(--danger-fg);
  }
</style>

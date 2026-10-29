{#if mail.sml}
  <vbox class="sml">
    {#if testSML}
      <vbox class="preview">
        <SMLDisplayKinds sml={mail.sml} message={mail} />
      </vbox>
    {:else}
      <SMLEditKinds sml={mail.sml} />
    {/if}
    <hbox class="buttons">
      <Button
        label={testSML ? $t`Edit` : $t`Preview`}
        icon={testSML ? EditIcon : PreviewIcon}
        onClick={() => testSML = !testSML} />
      <Button
        label={$t`Remove`}
        icon={RemoveIcon}
        onClick={onRemove} />
    </hbox>
  </vbox>
{/if}

<script lang="ts">
  import type { EMail } from "../../../logic/Mail/EMail";
  import SMLEditKinds from "../SML/SMLEditKinds.svelte";
  import SMLDisplayKinds from "../SML/SMLDisplayKinds.svelte";
  import Button from "../../Shared/Button.svelte";
  import PreviewIcon from "lucide-svelte/icons/check-line";
  import EditIcon from "lucide-svelte/icons/pencil";
  import RemoveIcon from "lucide-svelte/icons/trash-2";
  import { t } from "../../../l10n/l10n";

  export let mail: EMail;
  let testSML = false;

  function onRemove() {
    mail.sml = null;
    testSML = false;
  }
</script>

<style>
  .sml {
    margin: 16px 32px;
  }
  .sml .buttons {
    margin: 12px;
    gap: 12px;
  }
  .preview {
    height: 50vh;
  }

  :global(.fresh) .sml {
    margin: 16px 20px 0;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    background-color: var(--l2-bg);
  }
  :global(.fresh) .sml .buttons {
    margin: 12px 0 0;
    gap: 8px;
  }
</style>

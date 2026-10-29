<hbox class="password">
  <input type="password"
    placeholder={$t`Your password`}
    bind:value={password}
    bind:this={inputEl}
    required
    name="password"
    {autofocus}
    on:keydown={(event) => onKeyEnter(event, onEnter)}
    />
  <hbox class="buttons">
    <Button classes="cleartext"
      label={cleartext ? $t`Hide password` : $t`Show password`}
      onClick={() => cleartext = !cleartext}
      icon={cleartext ? EyeIcon : EyeOffIcon}
      iconOnly
      plain
      />
  </hbox>
</hbox>

<script lang="ts">
  import Button from "../../Shared/Button.svelte";
  import { onKeyEnter } from "../../Util/util";
  import EyeIcon from "lucide-svelte/icons/eye";
  import EyeOffIcon from "lucide-svelte/icons/eye-off";
  import { createEventDispatcher } from 'svelte';
  import { t } from "../../../l10n/l10n";
  const dispatchEvent = createEventDispatcher();

  /** in/out */
  export let password: string;
  export let autofocus = false;

  let cleartext = false;
  let inputEl: HTMLInputElement;
  $: if (inputEl) inputEl.type = cleartext ? "text" : "password";

  function onEnter() {
    if (password) {
      dispatchEvent("continue");
    }
  }

  export function focus() {
    inputEl.focus();
  }
</script>

<style>
  .password {
    margin: 8px 0 8px 0;
  }
  input {
    height: 24px;
  }
  .buttons {
    min-width: 32px;
  }
  :global(.fresh) .password {
    align-items: center;
    gap: 8px;
    margin: 0;
  }
  :global(.fresh) .password input {
    height: var(--control-height);
  }
  :global(.fresh .mail-address) + .password {
    margin-block-end: 12px;
  }
  :global(.fresh .mail-address) + .password input {
    height: var(--control-height-l);
    font-size: var(--text-l);
  }
  :global(.fresh .mail-address) + .password .buttons {
    min-width: 56px;
  }
</style>

<hbox class="mail-check" style="height: {height}px">
  {#if loggingIn}
    <LoginIcon size="24px" />
  {:else if checkingMail}
    <Spinner size="24px" />
  {:else if pullProgress > 0}
    <hbox class="pull-arrow" class:armed={pullProgress >= 1} style="opacity: {Math.min(pullProgress, 1)}">
      <FetchingIcon size="24px" />
    </hbox>
  {/if}
</hbox>

<script lang="ts">
  import type { Folder } from "../../../logic/Mail/Folder";
  import Spinner from "../../Shared/Spinner.svelte";
  import FetchingIcon from "lucide-svelte/icons/arrow-big-down-dash";
  import LoginIcon from "lucide-svelte/icons/key-round";

  export let folder: Folder;
  /** How far the user pulled the list down. 1 = far enough to check mail */
  export let pullProgress = 0;
  /** in px */
  export let height = 56;

  let checkingMail = false;
  let loggingIn = false;
  export async function onCheckMail() {
    try {
      loggingIn = true;
      let account = folder.account;
      if (!account.isLoggedIn) {
        await account.loginAndStartup(true);
      }
      loggingIn = false;
      checkingMail = true;
      await folder.getNewMessages();
    } finally {
      loggingIn = false;
      checkingMail = false;
    }
  }
</script>

<style>
  .mail-check {
    position: absolute;
    top: 0px;
    inset-inline: 0px;
    align-items: center;
    justify-content: center;
    color: grey;
  }
  .pull-arrow {
    transition: transform 120ms ease-out, color 120ms ease-out;
  }
  .pull-arrow.armed {
    transform: scale(1.2);
    color: var(--selected-bg);
  }
</style>

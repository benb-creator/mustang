<BasicButton {onClick} {page} {params}>
  <hbox class="stack" slot="icon">
    <Stack>
      <hbox class="icon1" flex>
        {#if isPictureURL(icon1)}
          <img src={icon1} width="24" height="24" alt="" />
        {:else}
          <AppIcon icon={icon1} size="24px" />
        {/if}
      </hbox>
      <hbox class="icon2" flex>
        {#if isPictureURL(icon2)}
          <img src={icon2} width="18" height="18" alt="" />
        {:else}
          <AppIcon icon={icon2} size="18px" />
        {/if}
      </hbox>
    </Stack>
  </hbox>
</BasicButton>

<script lang="ts">
  import { goTo } from "../selectedApp";
  import Stack from "../../Shared/Stack.svelte";
  import AppIcon from "../AppIcon.svelte";
  import BasicButton from "./BasicButton.svelte";

  export let icon1: ConstructorOfATypedSvelteComponent | string;
  export let icon2: ConstructorOfATypedSvelteComponent | string;
  export let onClick = onClickPage;
  export let page: string | null = null;
  export let params = {};

  function onClickPage() {
    goTo(page, params);
  }

  /** A person's picture is a URL, an app icon is SVG markup */
  function isPictureURL(icon: ConstructorOfATypedSvelteComponent | string): icon is string {
    return typeof(icon) == "string" && !icon.includes("<svg");
  }
</script>

<style>
  .stack :global(.stack) {
    width: 24px;
    height: 24px;
  }
  .icon1 {
    align-items: center;
    justify-content: center;
  }
  .icon1,
  .icon1 :global(.cls-1),
  .icon1 :global(.cls-2),
  .icon1 :global(.cls-3) {
    stroke: var(--button-border);
  }
  .icon1 :global(.date-calendar-icon) {
    display: none;
  }
  .icon2 {
    align-items: start;
    justify-content: end;
    color: var(--fg);
  }
  .icon2 :global(svg) {
    fill: var(--bg);
  }
  .stack img {
    border-radius: 50%;
    object-fit: cover;
  }
</style>

{#if $isDemo}
  <hbox class="demo-bar">
    <hbox class="text font-smallest">
      Demo
    </hbox>
  </hbox>
{/if}

<script lang="ts">
  import { isDemo } from "./demo";
</script>

<style>
  .demo-bar {
    align-items: center;
    background: linear-gradient(to top, #FFF160 60%, transparent 95%) !important;
    color: #160C27;
    width: 18px;
    height: 100%;
  }
  .text {
    transform: rotate(-90deg);
    font-weight: 500;
    text-transform: uppercase;
    width: 18px;
  }
  :global(.fresh) .demo-bar {
    background: linear-gradient(to top, var(--signal) 60%, transparent 95%) !important; /* the classic rule above has !important */
    color: var(--fg-on-signal);
  }
  :global(.fresh) .text {
    font-size: var(--text-xs);
    font-weight: 600;
  }
</style>

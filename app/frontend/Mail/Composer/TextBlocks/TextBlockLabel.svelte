<hbox class="text-block-label">
  <hbox class="keyword">::{block.keyword}</hbox>
  <hbox class="text">{block.text}</hbox>
</hbox>

<script lang="ts">
  import type { TextBlock } from "../../../../logic/Mail/TextBlock/TextBlock";

  export let block: TextBlock;
</script>

<style>
  .text-block-label {
    flex: 1 1 0;
    min-width: 0;
    align-items: baseline;
    gap: 12px;
  }
  .keyword {
    flex: none;
    font-weight: bold;
  }
  .text {
    display: block;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    opacity: 75%;
  }
</style>

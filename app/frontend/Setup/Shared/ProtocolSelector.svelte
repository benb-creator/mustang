<vbox class="protocol-selector">
  {#each protocols as protocol}
    <label class="protocol">
      <input type="radio" bind:group={selectedDescr} value={protocol} name="protocol" />
      <span class="name">{protocol.label}</span>
    </label>
  {/each}
</vbox>

<script lang="ts" context="module">
  export class ProtocolDescription {
    label: string;
    protocolID: string;
  }
</script>
<script lang="ts">
  /** in */
  export let protocols: ProtocolDescription[];
  /** in/out */
  export let selectedProtocol: string = protocols[0]?.protocolID;

  let selectedDescr: ProtocolDescription = protocols.find(p => p.protocolID == selectedProtocol) ?? protocols[0];
  $: selectedProtocol = selectedDescr?.protocolID;
</script>

<style>
  .protocol-selector {
    margin-block-start: 6px;
    align-items: start;
    margin-inline-end: 32px;
    padding-block-start: 4px;
  }
  .protocol {
    padding: 2px 20px 2px 12px;
    margin: 2px;
  }
  .name {
    margin-inline-start: 8px;
  }
  :global(.fresh) .protocol-selector {
    align-items: stretch;
    gap: 8px;
    margin: 0;
    padding: 0;
  }
  :global(.fresh) .protocol {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    box-sizing: border-box;
    margin: 0;
    padding: 0 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-m);
    font-weight: 500;
    cursor: pointer;
    transition: border-color var(--motion-fast) var(--motion-ease);
  }
  :global(.fresh) .protocol:hover {
    border-color: var(--fg-3);
  }
  :global(.fresh) .protocol:has(input:checked) {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  :global(.fresh) .protocol input {
    margin: 0;
  }
  :global(.fresh) .name {
    margin: 0;
  }
</style>

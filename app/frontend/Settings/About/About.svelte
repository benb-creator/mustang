<vbox class="app-logo">
  <Icon data={logo} size="20px" />
</vbox>
<h1>{appName} {appVersion}</h1>

<div>
  <T msg={$t`Copyright 2024 Ben Bucksch, #, and other contributors`}>
    <a href="{siteRoot}" target="_blank">{appName == "Parula" || appName == "Lookout" ? "Beonex GmbH" : "Mustang GmbH"}</a>
  </T>
</div>

<vbox class="update">
  <Update />
</vbox>

<script lang="ts">
  import { appName, appVersion, siteRoot } from '../../../logic/build';
  import Update from './Update.svelte';
  import Icon from 'svelte-icon/Icon.svelte';
  import T from '../../../l10n/T.svelte';
  import logo from '../../asset/icon/general/logo.svg?raw';
  import { t } from '../../../l10n/l10n';
</script>

<style>
  .update {
    margin-block-start: 24px;
  }
  :global(.mobile) .app-logo {
    align-items: center;
    padding-block-start: 24px;
    color: var(--selected-bg);
  }
  :global(.mobile) .app-logo :global(svg) {
    width: 72px;
    height: 72px;
  }
  :global(.mobile) .app-logo :global(svg :is(.horse, .circle-bars)) {
    fill: currentColor;
    stroke: currentColor;
  }
  :global(.mobile) .app-logo + h1 {
    text-align: center;
    font-size: 26px;
  }
</style>

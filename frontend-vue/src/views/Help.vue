<script setup lang="ts">
</script>

<template>
  <div>
    <div class="page-header">
      <h2>{{ $t('help.title') }}</h2>
      <p>{{ $t('help.description') }}</p>
    </div>

    <div class="card">
      <h3>{{ $t('help.about_title') }}</h3>
      <p style="color: var(--text-muted); line-height: 1.7;" v-html="$t('help.about_text')"></p>
    </div>

    <div class="card">
      <h3>{{ $t('help.scan_title') }}</h3>
      <p style="color: var(--text-muted); line-height: 1.7;" v-html="$t('help.scan_text')"></p>
      <ul style="color: var(--text-muted); line-height: 2; margin-top: 8px; padding-left: 20px;">
        <li v-html="$t('help.scan_support_fits')"></li>
        <li v-html="$t('help.scan_support_fits_gz')"></li>
        <li v-html="$t('help.scan_support_xisf')"></li>
      </ul>
    </div>

    <div class="card">
      <h3>{{ $t('help.db_title') }}</h3>
      <p style="color: var(--text-muted); line-height: 1.7;" v-html="$t('help.db_text')"></p>
    </div>
  </div>
</template>

<style scoped>
code.key {
  background: var(--surface2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  border: 1px solid var(--border);
}
</style>

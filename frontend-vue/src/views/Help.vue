<script setup lang="ts">
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Hilfe</h2>
      <p>Dokumentation und Tipps zu StellaShelf</p>
    </div>

    <div class="card">
      <h3>Über StellaShelf</h3>
      <p style="color: var(--text-muted); line-height: 1.7;">
        StellaShelf ist ein Open-Source-Tool zur Verwaltung und Katalogisierung von Astrofotografie-Bilddaten.
        Es extrahiert Metadaten aus FITS-Dateien, gruppiert sie in Beobachtungssitzungen und stellt alles
        über eine moderne Weboberfläche bereit.
      </p>
    </div>

    <div class="card">
      <h3>Scanning</h3>
      <p style="color: var(--text-muted); line-height: 1.7;">
        Wähle ein Verzeichnis mit FITS-Dateien aus und starte den Scan. StellaShelf extrahiert automatisch
        Metadaten (Zielobjekt, Kamera, Teleskop, Filter, Belichtungszeit etc.) aus den FITS-Headern.
      </p>
      <ul style="color: var(--text-muted); line-height: 2; margin-top: 8px; padding-left: 20px;">
        <li><strong>.fit / .fits</strong> — Standard FITS-Dateien</li>
        <li><strong>.fit.gz / .fits.gz</strong> — Gzip-komprimierte FITS (z.B. von SGP)</li>
        <li><strong>.xisf</strong> — XISF-Dateien werden erkannt aber noch nicht vollständig geparst</li>
      </ul>
    </div>

    <div class="card">
      <h3>Tastenkürzel</h3>
      <table class="data-table">
        <thead><tr><th>Aktion</th><th>Kürzel</th></tr></thead>
        <tbody>
          <tr><td>Dashboard</td><td><code class="key">Strg + 1</code></td></tr>
          <tr><td>Targets</td><td><code class="key">Strg + 2</code></td></tr>
          <tr><td>Sessions</td><td><code class="key">Strg + 3</code></td></tr>
          <tr><td>Suche</td><td><code class="key">Strg + K</code></td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Datenbank</h3>
      <p style="color: var(--text-muted); line-height: 1.7;">
        Die Datenbank wird standardmäßig unter <code>~/.stellashelf/stellashelf.db</code> gespeichert.
        Du kannst den Pfad über die <RouterLink to="/settings">Einstellungen</RouterLink> ändern.
      </p>
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

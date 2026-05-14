<script setup lang="ts">
defineProps<{
  value: string | number
  label: string
}>()
</script>

<template>
  <div class="stat-card">
    <div class="value">{{ value }}</div>
    <div class="label">{{ label }}</div>
  </div>
</template>

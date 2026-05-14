<script setup lang="ts">
const props = defineProps<{
  total: number
  page: number
  pages: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
}>()
</script>

<template>
  <div class="pagination" v-if="pages > 1">
    <span class="info">{{ total }} Ergebnisse, Seite {{ page }} von {{ pages }}</span>
    <button :disabled="page <= 1" @click="emit('update:page', page - 1)">&laquo;</button>
    <button class="active">{{ page }}</button>
    <button :disabled="page >= pages" @click="emit('update:page', page + 1)">&raquo;</button>
  </div>
</template>

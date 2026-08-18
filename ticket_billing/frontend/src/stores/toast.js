import { defineStore } from 'pinia'
import { ref } from 'vue'

// Kurze Rückmeldungen zu Aktionen. Bewusst minimal — es geht nur darum, dass
// eine gebuchte Zeit oder eine Umverteilung sichtbar quittiert wird.
export const useToastStore = defineStore('toast', () => {
  const items = ref([])
  let counter = 0

  function push(text, type = 'success', duration = 4000) {
    const id = ++counter
    items.value.push({ id, text, type })
    setTimeout(() => remove(id), duration)
  }

  function remove(id) {
    items.value = items.value.filter((t) => t.id !== id)
  }

  return {
    items,
    remove,
    success: (text) => push(text, 'success'),
    error: (text) => push(text, 'error', 6000),
    info: (text) => push(text, 'info'),
  }
})

import './assets/main.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import i18n from './i18n'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

// Sprache am <html>-Element spiegeln (Vorlesehilfen, Silbentrennung).
document.documentElement.setAttribute('lang', i18n.global.locale.value)

app.mount('#app')

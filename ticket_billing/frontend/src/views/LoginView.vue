<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="w-full max-w-sm">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold">{{ t('app.name') }}</h1>
          <p class="text-sm text-slate-500">{{ t('app.tagline') }}</p>
        </div>
        <LanguageSwitcher />
      </div>

      <form class="card card-body space-y-4" @submit.prevent="submit">
        <h2 class="text-lg font-semibold">{{ t('login.title') }}</h2>

        <div>
          <label class="label" for="usr">{{ t('login.user') }}</label>
          <input id="usr" v-model="usr" type="text" class="input" autocomplete="username" required />
        </div>

        <div>
          <label class="label" for="pwd">{{ t('login.password') }}</label>
          <input
            id="pwd"
            v-model="pwd"
            type="password"
            class="input"
            autocomplete="current-password"
            required
          />
        </div>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

        <button class="btn-primary w-full" type="submit" :disabled="busy">
          {{ t('login.submit') }}
        </button>
      </form>

      <!-- Schnell-Logins. Sie erscheinen nur, wenn der Server Demo-Daten
           meldet — ohne installierte Demo lehnt auch der Anmelde-Endpunkt
           ab, das Ausblenden hier ist also nur die Anzeige davon. -->
      <div v-if="demoUsers.length" class="card card-body mt-4">
        <div class="flex items-baseline justify-between gap-2 mb-3">
          <h3 class="text-sm font-semibold text-slate-700">{{ t('login.demo_title') }}</h3>
          <span class="text-xs text-amber-700">{{ t('login.demo_warning') }}</span>
        </div>

        <div class="space-y-2">
          <button
            v-for="u in demoUsers"
            :key="u.user"
            class="btn-secondary w-full !justify-start"
            :disabled="busy"
            @click="loginAs(u)"
          >
            <span class="font-medium">{{ u.name }}</span>
            <span class="text-slate-400 text-xs">{{ u.role_label }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { api } from '@/utils/api'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const session = useSessionStore()
const router = useRouter()
const route = useRoute()

const usr = ref('')
const pwd = ref('')
const busy = ref(false)
const error = ref('')

function goOn() {
  // Nach der Anmeldung dorthin, wo der Nutzer hinwollte -- sonst in den
  // weitesten Bereich, den seine Rolle hergibt.
  const target = route.query.weiter
  router.replace(typeof target === 'string' && target ? target : session.homeRoute)
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await session.login(usr.value, pwd.value)
    goOn()
  } catch (e) {
    error.value = e.message || t('login.failed')
  } finally {
    busy.value = false
  }
}

const demoUsers = ref([])

async function loadDemo() {
  try {
    const status = await api.getDemoStatus()
    demoUsers.value = status?.users || []
  } catch {
    demoUsers.value = []
  }
}

async function loginAs(user) {
  busy.value = true
  error.value = ''
  try {
    await api.demoLogin(user.user)
    // Sitzung frisch holen: Rollen und Abteilung entscheiden, wohin es geht.
    await session.load(true)
    goOn()
  } catch (e) {
    error.value = e.message || t('login.failed')
  } finally {
    busy.value = false
  }
}

onMounted(loadDemo)
</script>

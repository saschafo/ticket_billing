/**
 * Absichtlich schmal gehalten: Diese Prüfung soll Fehler finden, nicht
 * Geschmacksfragen klären. Formatierung bleibt außen vor, damit ein roter
 * Lauf immer etwas bedeutet.
 *
 * Anlass war ein `computed()` ohne zugehörigen Import. Der Build übersetzt
 * das anstandslos -- für den Compiler ist es eine globale Variable, die es
 * zur Laufzeit vielleicht gibt. Erst im Browser wirft die Komponente, und
 * eine Komponente, die beim Aufbau wirft, rendert wortlos nichts.
 */
import js from '@eslint/js'
import vue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  { ignores: ['dist/**', 'node_modules/**', '../public/frontend/**'] },
  js.configs.recommended,
  // 'essential' statt 'recommended': nur Regeln gegen echte Fehler.
  ...vue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
    },
    rules: {
      'no-undef': 'error',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
]

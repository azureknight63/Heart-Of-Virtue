import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

/**
 * ESLint 9 flat config for the Heart of Virtue frontend.
 *
 * The `lint` npm script and the eslint/react/react-hooks devDependencies were
 * already declared in package.json, but no config file existed, so `npm run
 * lint` failed outright. This restores it.
 *
 * react-hooks is the point of the exercise: `rules-of-hooks` and
 * `exhaustive-deps` catch the stale-closure and missing-cleanup bugs this
 * codebase is most prone to. `exhaustive-deps` is set to `warn` (its upstream
 * default) so it advises without failing the build on intentional omissions.
 *
 * File selection lives in the `files` globs below, NOT in the npm script. The
 * `lint` script used to pass `--ext .jsx,.js`, which flat config ignores (and
 * ESLint 10 rejects outright); it was a no-op that read as the real source of
 * truth. Verified identical before removal: 201 files, 140 messages either way.
 */
export default [
  {
    ignores: ['dist/**', 'coverage/**', 'node_modules/**', 'public/**'],
  },
  js.configs.recommended,
  react.configs.flat.recommended,
  react.configs.flat['jsx-runtime'],
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
        // A few modules detect the test environment via
        // `typeof process !== 'undefined' && process.env.VITEST`. The `typeof`
        // guard makes that safe in the browser bundle, where `process` is
        // genuinely absent — declare it so `no-undef` doesn't flag the guard.
        process: 'readonly',
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      // The project uses runtime prop shapes from the Python engine rather than
      // PropTypes; enforcing them would be noise, not safety.
      'react/prop-types': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
  {
    // Vitest + Testing Library specs run in jsdom with test globals.
    files: ['**/*.test.{js,jsx}', 'src/test/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.vitest,
      },
    },
  },
  {
    // Node-side build/tooling scripts.
    files: ['scripts/**/*.{js,mjs}', '*.config.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
]

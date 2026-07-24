import { createApp } from 'vue'
import { createPinia } from 'pinia'

/** FontAwesome 图标库 — 导入全部 Solid 图标 */
import { library } from '@fortawesome/fontawesome-svg-core'
import { fas } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

library.add(fas)

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.component('font-awesome-icon', FontAwesomeIcon)
app.use(createPinia())
app.use(router)
app.mount('#app')

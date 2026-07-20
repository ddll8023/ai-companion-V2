import { createApp } from 'vue'
import { createPinia } from 'pinia'

/** FontAwesome 图标库 */
import { library } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import {
  faBrain,
  faBullseye,
  faCircleExclamation,
  faClock,
  faComments,
  faDatabase,
  faFolder,
  faGear,
  faHammer,
  faHouse,
  faInbox,
  faServer,
  faSpinner,
} from '@fortawesome/free-solid-svg-icons'

library.add(
  faBrain,
  faBullseye,
  faCircleExclamation,
  faClock,
  faComments,
  faDatabase,
  faFolder,
  faGear,
  faHammer,
  faHouse,
  faInbox,
  faServer,
  faSpinner,
)

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.component('font-awesome-icon', FontAwesomeIcon)
app.use(createPinia())
app.use(router)
app.mount('#app')

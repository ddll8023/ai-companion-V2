import { createApp } from 'vue'
import { createPinia } from 'pinia'

/** FontAwesome 图标库 */
import { library } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import {
  faBrain,
  faBullseye,
  faCheckCircle,
  faCircleExclamation,
  faClock,
  faCommentDots,
  faComments,
  faDatabase,
  faFolder,
  faGear,
  faHammer,
  faHouse,
  faInbox,
  faKey,
  faMessage,
  faPaperPlane,
  faPen,
  faPlug,
  faPlus,
  faServer,
  faSpinner,
  faStop,
  faTrash,
} from '@fortawesome/free-solid-svg-icons'

library.add(
  faBrain,
  faBullseye,
  faCheckCircle,
  faCircleExclamation,
  faClock,
  faCommentDots,
  faComments,
  faDatabase,
  faFolder,
  faGear,
  faHammer,
  faHouse,
  faInbox,
  faKey,
  faMessage,
  faPaperPlane,
  faPen,
  faPlug,
  faPlus,
  faServer,
  faSpinner,
  faStop,
  faTrash,
)

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.component('font-awesome-icon', FontAwesomeIcon)
app.use(createPinia())
app.use(router)
app.mount('#app')

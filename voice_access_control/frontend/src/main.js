import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./assets/theme.css";
import App from "./App.vue";
import router from "./router";
import { setAuthToken } from "./api";

const token = localStorage.getItem("token");
if (token) {
  setAuthToken(token);
}

const app = createApp(App);
app.use(ElementPlus);
app.use(router);
app.mount("#app");

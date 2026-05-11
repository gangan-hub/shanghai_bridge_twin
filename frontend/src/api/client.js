import axios from "axios";
import { useAuthStore } from "../stores/auth.js";
import { ElMessage, ElMessageBox } from "element-plus";

const client = axios.create({
  baseURL: "/api",
  timeout: 120000, // 改为 2 分钟 (之前 30 秒对 AI 推理完全不够)
});

client.interceptors.request.use((config) => {
  const store = useAuthStore();
  if (store.token) {
    config.headers.Authorization = `Bearer ${store.token}`;
  }
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      const store = useAuthStore();
      if (store.token) {
        ElMessageBox.alert("您的登录会话已过期，请重新登录。", "会话过期", {
          confirmButtonText: "确定",
          callback: () => {
            store.logout();
            window.location.reload();
          },
        });
      }
    } else {
      const msg = err.response?.data?.message || "服务器连接失败";
      ElMessage.error(msg);
    }
    return Promise.reject(err);
  }
);

export default client;

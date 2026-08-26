import axios from "axios";
import { useAuthStore } from "../stores/auth.js";
import { ElMessage, ElMessageBox } from "element-plus";

/* ================= 请求环境配置 =================
   - baseURL:      开发环境走 Vite 代理(/api)，生产可用 VITE_API_BASE 覆盖
   - timeout:      默认 30s；AI 推演等长请求在调用处单独传 { timeout }
   - retry:        网络层错误(GET)自动重试，幂等安全
   - 401:          会话过期统一弹窗并登出
================================================ */

const RETRY_TIMES = Number(import.meta.env.VITE_API_RETRY ?? 2); // 网络错误重试次数
const RETRY_DELAY = 600; // 重试间隔 ms

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  timeout: 30000,
  // 跨域携带 cookie（后端同域部署时可忽略）
  withCredentials: false,
});

/* ---------- 请求拦截器：注入 Token ---------- */
client.interceptors.request.use((config) => {
  const store = useAuthStore();
  if (store.token) {
    config.headers.Authorization = `Bearer ${store.token}`;
  }
  return config;
});

/* ---------- 响应拦截器：401 统一处理 ---------- */
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

/* ---------- GET 幂等请求网络错误自动重试 ----------
   仅对「请求根本没到服务器」的错误重试：
   ECONNABORTED(超时) / ERR_NETWORK(断网/DNS) / 无 response 的错误
   HTTP 4xx/5xx 业务错误不重试 */
client.interceptors.response.use(undefined, async (err) => {
  const config = err.config;
  if (!config || config.method !== "get" || config._retried >= RETRY_TIMES) {
    throw err;
  }
  const noResponse =
    !err.response ||
    err.code === "ECONNABORTED" ||
    err.code === "ERR_NETWORK";
  if (!noResponse) throw err;

  config._retried = (config._retried || 0) + 1;
  await new Promise((res) => setTimeout(res, RETRY_DELAY * config._retried));
  return client.request(config);
});

/* ---------- 常用快捷方法（返回 data 而非 AxiosResponse） ---------- */
export const api = {
  get: (url, config) => client.get(url, config).then((r) => r.data),
  post: (url, data, config) => client.post(url, data, config).then((r) => r.data),
  put: (url, data, config) => client.put(url, data, config).then((r) => r.data),
  delete: (url, config) => client.delete(url, config).then((r) => r.data),
};

export default client;

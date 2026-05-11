import { defineStore } from "pinia";
import client from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("token") || "",
    user: null,
  }),
  actions: {
    async login(username, password) {
      const { data } = await client.post("/auth/login", { username, password });
      this.token = data.token;
      this.user = data.user;
      localStorage.setItem("token", data.token);
    },
    logout() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("token");
    },
  },
});

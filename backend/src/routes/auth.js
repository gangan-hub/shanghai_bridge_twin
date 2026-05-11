import express from "express";
import bcrypt from "bcryptjs";
import { query } from "../db.js";
import { signToken } from "../auth.js";

const router = express.Router();

router.post("/login", async (req, res) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ message: "username and password required" });
    }

    const result = await query(
      "SELECT id, username, password_hash, role FROM users WHERE username = $1 LIMIT 1",
      [username]
    );

    const user = result.rows[0];
    if (!user) {
      return res.status(401).json({ message: "Invalid credentials" });
    }

    const valid =
      user.password_hash === password ||
      (await bcrypt.compare(password, user.password_hash));
    if (!valid) {
      return res.status(401).json({ message: "Invalid credentials" });
    }

    const token = signToken({
      id: user.id,
      username: user.username,
      role: user.role,
    });

    return res.json({
      token,
      user: { id: user.id, username: user.username, role: user.role },
    });
  } catch (error) {
    return res.status(500).json({ message: "Login failed", detail: error.message });
  }
});

export default router;

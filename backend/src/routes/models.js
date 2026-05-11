import express from "express";
import { authRequired } from "../auth.js";

const router = express.Router();

router.get("/:bridgeCode/tileset", authRequired, async (req, res) => {
  const { bridgeCode } = req.params;
  return res.json({
    bridgeCode,
    tilesetUrl: `/models/${bridgeCode}/tileset.json`,
  });
});

export default router;

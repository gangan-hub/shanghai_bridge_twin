import dotenv from "dotenv";
import { runMigrations } from "../src/migrate.js";

dotenv.config();

runMigrations()
  .then(() => {
    console.log("repair: done");
    process.exit(0);
  })
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });

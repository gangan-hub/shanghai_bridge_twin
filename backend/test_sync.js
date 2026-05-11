import jwt from "jsonwebtoken";
const token = jwt.sign({id:1,username:"admin",role:"admin"},"replace_with_strong_secret",{expiresIn:"1h"});
const res = await fetch("http://localhost:3001/api/admin/sync-pois", {
  method: "POST",
  headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
});
const body = await res.text();
console.log(`Status: ${res.status}`);
console.log(`Body: ${body}`);

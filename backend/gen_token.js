import jwt from "jsonwebtoken";
console.log(jwt.sign({id:1,username:"admin",role:"admin"},"replace_with_strong_secret",{expiresIn:"1h"}));

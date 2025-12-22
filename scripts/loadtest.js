import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 20,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"], // < 1% errors
  },
};

const BASE_URL = "http://localhost:8080";
const HOSTS = ["foo.localhost", "bar.localhost"];

export default () => {
  // Randomly pick a host (50/50)
  const host = HOSTS[Math.floor(Math.random() * HOSTS.length)];

  const res = http.get(`${BASE_URL}/`, {
    headers: {
      Host: host,
    },
  });

  check(res, {
    "status is 200": (r) => r.status === 200,
  });

  sleep(0.1);
};

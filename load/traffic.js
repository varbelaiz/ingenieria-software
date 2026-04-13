import http from "k6/http";
import { check, sleep } from "k6";

const API_BASE_URL = __ENV.API_BASE_URL || "http://127.0.0.1:8000";
const API_KEY = __ENV.API_KEY || "api_key";
const TRAFFIC_PROFILE = (__ENV.TRAFFIC_PROFILE || "seed").toLowerCase();

const VALID_WELL_IDS = ["POZO-001", "POZO-002", "POZO-003"];
const WELL_DATE = "2026-03-25";
const FORECAST_START = "2026-03-25";
const FORECAST_END = "2026-03-27";

export const options = profileOptions(TRAFFIC_PROFILE);

function profileOptions(profile) {
  if (profile === "realistic") {
    return {
      vus: 2,
      duration: "30s",
      thresholds: {
        checks: ["rate==1.0"],
      },
    };
  }

  return {
    vus: 1,
    iterations: 8,
    thresholds: {
      checks: ["rate==1.0"],
    },
  };
}

function buildHeaders(apiKey) {
  return {
    headers: {
      "X-API-Key": apiKey,
    },
  };
}

function callWellsOk() {
  const response = http.get(
    `${API_BASE_URL}/api/v1/wells?date_query=${WELL_DATE}`,
    buildHeaders(API_KEY)
  );
  check(response, {
    "wells_ok returns 200": (res) => res.status === 200,
  });
  return response;
}

function callForecastOk() {
  const wellId =
    VALID_WELL_IDS[Math.floor(Math.random() * VALID_WELL_IDS.length)];
  const response = http.get(
    `${API_BASE_URL}/api/v1/forecast?id_well=${wellId}&date_start=${FORECAST_START}&date_end=${FORECAST_END}`,
    buildHeaders(API_KEY)
  );
  check(response, {
    "forecast_ok returns 200": (res) => res.status === 200,
  });
  return response;
}

function callForbiddenKey() {
  const response = http.get(
    `${API_BASE_URL}/api/v1/wells?date_query=${WELL_DATE}`,
    buildHeaders("invalid-key")
  );
  check(response, {
    "forbidden_key returns 403": (res) => res.status === 403,
  });
  return response;
}

function callForecastNotFound() {
  const response = http.get(
    `${API_BASE_URL}/api/v1/forecast?id_well=POZO-999&date_start=${FORECAST_START}&date_end=${FORECAST_END}`,
    buildHeaders(API_KEY)
  );
  check(response, {
    "forecast_not_found returns 404": (res) => res.status === 404,
  });
  return response;
}

function runSeedCycle() {
  callWellsOk();
  sleep(0.2);
  callForecastOk();
  sleep(0.2);
  callForbiddenKey();
  sleep(0.2);
  callForecastNotFound();
  sleep(0.2);
}

function runRealisticCycle() {
  const roll = Math.random();

  if (roll < 0.75) {
    callForecastOk();
  } else if (roll < 0.93) {
    callWellsOk();
  } else if (roll < 0.97) {
    callForbiddenKey();
  } else {
    callForecastNotFound();
  }

  sleep(0.4);
}

export default function () {
  if (TRAFFIC_PROFILE === "realistic") {
    runRealisticCycle();
    return;
  }

  runSeedCycle();
}

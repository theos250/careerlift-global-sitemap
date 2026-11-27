import { createHmac, timingSafeEqual } from "node:crypto";

function isExpectedTopic(value) {
  try {
    const topic = new URL(value);
    const customDomainTopic =
      ["www.careerliftglobal.com", "careerliftglobal.com"].includes(topic.hostname) &&
      topic.pathname === "/feeds/posts/default";
    const bloggerCanonicalTopic =
      topic.hostname === "www.blogger.com" &&
      /^\/feeds\/[0-9]+\/posts\/default$/.test(topic.pathname);
    return topic.protocol === "https:" &&
      (customDomainTopic || bloggerCanonicalTopic) &&
      topic.searchParams.get("alt") === "atom";
  } catch {
    return false;
  }
}

const OWNER = "theos250";
const REPO = "careerlift-global-sitemap";
const WORKFLOW = "deploy-netlify.yml";
const MAX_BODY_BYTES = 1_000_000;

function logEvent(event, details = {}) {
  // Deliberately exclude query strings, challenge values, payloads, and credentials.
  console.info(JSON.stringify({ component: "blogger-websub", event, ...details }));
}

function response(statusCode, body, contentType = "text/plain; charset=utf-8") {
  return new Response(body, {
    status: statusCode,
    headers: { "content-type": contentType, "cache-control": "no-store" },
  });
}

function validSignature(rawBody, header, secret) {
  if (!header || !secret) return false;
  const match = /^(sha1|sha256)=([a-f0-9]+)$/i.exec(header.trim());
  if (!match) return false;
  const digest = createHmac(match[1].toLowerCase(), secret).update(rawBody).digest("hex");
  const supplied = match[2].toLowerCase();
  if (digest.length !== supplied.length) return false;
  return timingSafeEqual(Buffer.from(digest, "hex"), Buffer.from(supplied, "hex"));
}

export default async (request) => {
  const url = new URL(request.url);

  if (request.method === "GET") {
    const mode = url.searchParams.get("hub.mode");
    const topic = url.searchParams.get("hub.topic");
    const challenge = url.searchParams.get("hub.challenge");
    const validMode = ["subscribe", "unsubscribe"].includes(mode);
    const validTopic = isExpectedTopic(topic || "");
    const hasChallenge = Boolean(challenge);

    if (!validMode || !validTopic || !hasChallenge) {
      logEvent("verification_rejected", {
        method: "GET",
        mode: validMode ? mode : "invalid_or_missing",
        validTopic,
        hasChallenge,
        responseStatus: 400,
      });
      return response(400, "Invalid WebSub verification request");
    }

    logEvent("verification_accepted", {
      method: "GET",
      mode,
      responseStatus: 200,
    });
    return response(200, challenge);
  }

  if (request.method !== "POST") {
    logEvent("method_rejected", { method: request.method, responseStatus: 405 });
    return response(405, "Method not allowed");
  }

  logEvent("notification_received", { method: "POST" });

  const secret = process.env.WEBSUB_SECRET;
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!secret || !token) {
    logEvent("notification_configuration_missing", {
      hasWebSubSecret: Boolean(secret),
      hasGitHubDispatchToken: Boolean(token),
      responseStatus: 503,
    });
    return response(503, "Webhook is not configured");
  }

  const rawBody = Buffer.from(await request.arrayBuffer());
  if (rawBody.length === 0 || rawBody.length > MAX_BODY_BYTES) {
    logEvent("notification_size_rejected", {
      bodyBytes: rawBody.length,
      responseStatus: 413,
    });
    return response(413, "Invalid notification size");
  }

  const signatureIsValid = validSignature(
    rawBody,
    request.headers.get("x-hub-signature"),
    secret,
  );
  if (!signatureIsValid) {
    logEvent("notification_signature_rejected", { responseStatus: 401 });
    return response(401, "Invalid WebSub signature");
  }

  logEvent("notification_signature_accepted", { bodyBytes: rawBody.length });

  try {
    const githubResponse = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          "Accept": "application/vnd.github+json",
          "Authorization": `Bearer ${token}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": "CareerLiftGlobal-WebSub-Bridge",
        },
        body: JSON.stringify({ ref: "main" }),
      },
    );

    if (githubResponse.status !== 204) {
      logEvent("workflow_dispatch_rejected", {
        githubStatus: githubResponse.status,
        responseStatus: 502,
      });
      return response(502, "Could not trigger sitemap refresh");
    }

    logEvent("workflow_dispatch_accepted", {
      githubStatus: 204,
      responseStatus: 202,
    });
    return response(202, "Sitemap refresh requested");
  } catch (error) {
    logEvent("workflow_dispatch_error", {
      errorName: error instanceof Error ? error.name : "UnknownError",
      responseStatus: 502,
    });
    return response(502, "Could not trigger sitemap refresh");
  }
};

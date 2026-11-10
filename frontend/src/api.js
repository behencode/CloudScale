const BASE = import.meta.env.VITE_API_BASE || "";

function errorMessage(data, status) {
  if (!data) {
    return `Request failed (${status}).`;
  }
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item.msg || "Check the form and try again.")
      .join(" ");
  }
  return `Request failed (${status}).`;
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = localStorage.getItem("cc_token");
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`${BASE}${path}`, { ...options, headers, body });
  } catch (_error) {
    throw new Error("The CampusConnect API is not reachable. Start the backend on port 8000.");
  }
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (_parseError) {
      throw new Error(
        response.ok
          ? "The API returned a response that was not JSON."
          : `Request failed (${response.status}).`
      );
    }
  }
  if (!response.ok) {
    throw new Error(errorMessage(data, response.status));
  }
  return data;
}

async function cognitoRequest(operation, payload) {
  const region = import.meta.env.VITE_COGNITO_REGION;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  if (!region || !clientId) {
    throw new Error(
      "Cognito mode is selected, but VITE_COGNITO_REGION or VITE_COGNITO_CLIENT_ID is missing. Local login was not used."
    );
  }
  const response = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${operation}`,
    },
    body: JSON.stringify({ ClientId: clientId, ...payload }),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = data.message || data.__type || "Amazon Cognito rejected the sign-in.";
    throw new Error(message);
  }
  return data;
}

export async function cognitoLogin(email, password) {
  const data = await cognitoRequest("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  const token = data.AuthenticationResult && data.AuthenticationResult.IdToken;
  if (!token) {
    throw new Error("Amazon Cognito did not return an ID token.");
  }
  return token;
}

export function cognitoSignUp({ name, email, password }) {
  return cognitoRequest("SignUp", {
    Username: email,
    Password: password,
    UserAttributes: [
      { Name: "email", Value: email },
      { Name: "name", Value: name },
    ],
  });
}

export function cognitoConfirmSignUp(email, confirmationCode) {
  return cognitoRequest("ConfirmSignUp", {
    Username: email,
    ConfirmationCode: confirmationCode,
  });
}

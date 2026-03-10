import Keycloak from "keycloak-js";

const readRequiredValue = (value: string | undefined, label: string) => {
  if (!value) {
    return `${label} is missing. Copy apps/web/.env.example to apps/web/.env and fill it in.`;
  }
  return undefined;
};

const configError =
  readRequiredValue(import.meta.env.VITE_KEYCLOAK_URL, "VITE_KEYCLOAK_URL") ??
  readRequiredValue(import.meta.env.VITE_KEYCLOAK_REALM, "VITE_KEYCLOAK_REALM") ??
  readRequiredValue(import.meta.env.VITE_KEYCLOAK_CLIENT_ID, "VITE_KEYCLOAK_CLIENT_ID");

let keycloakClient: Keycloak | undefined;
let initPromise: Promise<boolean> | undefined;

export const getAuthConfigError = () => configError;

export const getControlApiBaseUrl = () =>
  import.meta.env.VITE_CONTROL_API_BASE_URL ?? "http://localhost:8000";

export const getStepUpAcr = () =>
  import.meta.env.VITE_KEYCLOAK_STEP_UP_ACR ?? "urn:qaongdur:loa:2";

export const getKeycloakAdminUsersUrl = () => {
  if (configError) {
    return undefined;
  }

  const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL!;
  const realm = import.meta.env.VITE_KEYCLOAK_REALM!;
  return `${keycloakUrl}/admin/${realm}/console/#/${realm}/users`;
};

export const getKeycloakClient = () => {
  if (configError) {
    throw new Error(configError);
  }

  keycloakClient ??= new Keycloak({
    url: import.meta.env.VITE_KEYCLOAK_URL!,
    realm: import.meta.env.VITE_KEYCLOAK_REALM!,
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID!,
  });

  return keycloakClient;
};

export const initKeycloak = () => {
  initPromise ??= getKeycloakClient().init({
    onLoad: "check-sso",
    pkceMethod: "S256",
    checkLoginIframe: false,
    enableLogging: import.meta.env.DEV,
  });

  return initPromise;
};

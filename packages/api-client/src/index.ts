import type { VmsApiClient } from "@qaongdur/types";
import { mockApiClient } from "./mock-api-client";
import { MockRealtimeEventSocket } from "./mock-event-socket";

export * from "./mock-event-socket";

export const createApiClient = (): VmsApiClient => mockApiClient;

export const createRealtimeSocket = () => new MockRealtimeEventSocket();

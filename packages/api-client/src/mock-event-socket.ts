import type { RealtimeEvent } from "@qaongdur/types";
import { mockData } from "./mock-data";

export type RealtimeEventHandler = (event: RealtimeEvent) => void;
export type RealtimeEventMode = "mock" | "disabled";

export interface RealtimeEventSocket {
  readonly mode: RealtimeEventMode;
  connect(): void;
  disconnect(): void;
  subscribe(handler: RealtimeEventHandler): () => void;
}

export class MockRealtimeEventSocket implements RealtimeEventSocket {
  readonly mode = "mock" as const;
  private handlers = new Set<RealtimeEventHandler>();
  private timerId: ReturnType<typeof setInterval> | undefined;

  connect() {
    if (this.timerId) {
      return;
    }

    this.timerId = setInterval(() => {
      const random = Math.random();
      if (random < 0.65) {
        const alert = mockData.alerts[Math.floor(Math.random() * mockData.alerts.length)];
        this.emit({ type: "alert.created", payload: alert });
        return;
      }

      const camera = mockData.cameras[Math.floor(Math.random() * mockData.cameras.length)];
      const states = ["healthy", "warning", "critical", "offline"] as const;
      const nextHealth = states[Math.floor(Math.random() * states.length)];
      this.emit({
        type: "camera.health_changed",
        payload: {
          cameraId: camera.id,
          health: nextHealth,
          happenedAt: new Date().toISOString(),
        },
      });
    }, 8000);
  }

  disconnect() {
    if (!this.timerId) {
      return;
    }
    clearInterval(this.timerId);
    this.timerId = undefined;
  }

  subscribe(handler: RealtimeEventHandler) {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  private emit(event: RealtimeEvent) {
    this.handlers.forEach((handler) => handler(event));
  }
}

export class DisabledRealtimeEventSocket implements RealtimeEventSocket {
  readonly mode = "disabled" as const;

  connect() {}

  disconnect() {}

  subscribe(_: RealtimeEventHandler) {
    return () => {};
  }
}

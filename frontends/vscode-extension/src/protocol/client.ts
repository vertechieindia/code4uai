/**
 * code4u.ai IDE Protocol Client
 * 
 * This is NOT REST spam.
 * It's a contracted execution protocol.
 * 
 * IDE Safeguards:
 * - Diff preview mandatory
 * - Ownership warnings inline
 * - Breaking-change badges
 * - One-click rollback
 * 
 * The IDE never executes anything automatically.
 */

import * as vscode from 'vscode';

// ============================================================
// Protocol Types
// ============================================================

export interface CursorContext {
  file: string;
  line: number;
  column: number;
  selection_start?: number;
  selection_end?: number;
  selection_text?: string;
}

export interface IntentRequest {
  intent: 'refactor' | 'add_api' | 'fix_bug' | 'explain' | 'rename' | 'extract';
  cursor: CursorContext;
  selection: string;
  instruction: string;
  workspace_id: string;
  user_id: string;
  preview_only: boolean;
  include_tests: boolean;
}

export interface ImpactedComponent {
  name: string;
  type: string;
  path: string;
  owner?: string;
  breaking: boolean;
}

export interface ValidationResult {
  types: 'pass' | 'fail' | 'pending';
  schemas: 'pass' | 'fail' | 'pending';
  tests: 'pass' | 'fail' | 'pending' | 'skipped';
  ownership: 'pass' | 'warning' | 'fail';
}

export interface DiffItem {
  diff_id: string;
  file_path: string;
  diff_content: string;
  language: string;
  lines_added: number;
  lines_removed: number;
  is_breaking: boolean;
  owner?: string;
}

export interface ExecutionUpdate {
  execution_id: string;
  state: string;
  summary: string;
  impacted_components: ImpactedComponent[];
  breaking_change: boolean;
  phase: string;
  progress: number;
  timestamp: string;
}

export interface DiffPayload {
  execution_id: string;
  state: 'READY_FOR_REVIEW';
  diffs: DiffItem[];
  validation: ValidationResult;
  summary: string;
  total_files: number;
  total_lines_added: number;
  total_lines_removed: number;
  breaking_changes: string[];
  ownership_warnings: string[];
}

export interface ErrorResponse {
  execution_id?: string;
  error: string;
  error_code: string;
  details?: Record<string, unknown>;
  recoverable: boolean;
}

export interface WebSocketMessage {
  type: 'intent_request' | 'execution_update' | 'diff_payload' | 'apply_request' | 'reject_request' | 'error' | 'ping' | 'pong';
  payload: Record<string, unknown>;
  timestamp: string;
  request_id?: string;
}

// ============================================================
// Protocol Client
// ============================================================

export type MessageHandler = (message: WebSocketMessage) => void;

export class Code4uProtocolClient {
  private ws: WebSocket | null = null;
  private readonly serverUrl: string;
  private readonly workspaceId: string;
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private pendingRequests: Map<string, {
    resolve: (value: unknown) => void;
    reject: (error: Error) => void;
  }> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: NodeJS.Timer | null = null;

  constructor(serverUrl: string, workspaceId: string) {
    this.serverUrl = serverUrl;
    this.workspaceId = workspaceId;
  }

  /**
   * Connect to the code4u.ai backend.
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = `${this.serverUrl}/ws/${this.workspaceId}`;
      
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.startPingInterval();
        resolve();
      };

      this.ws.onclose = (event) => {
        this.stopPingInterval();
        this.handleDisconnect(event);
      };

      this.ws.onerror = (error) => {
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    });
  }

  /**
   * Disconnect from the backend.
   */
  disconnect(): void {
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send an intent request and stream updates.
   */
  async sendIntent(
    request: IntentRequest,
    onUpdate: (update: ExecutionUpdate) => void,
    onDiff: (payload: DiffPayload) => void,
    onError: (error: ErrorResponse) => void
  ): Promise<void> {
    const requestId = this.generateRequestId();

    // Set up handlers for this request
    const handler: MessageHandler = (message) => {
      if (message.request_id !== requestId) return;

      switch (message.type) {
        case 'execution_update':
          onUpdate(message.payload as unknown as ExecutionUpdate);
          break;
        case 'diff_payload':
          onDiff(message.payload as unknown as DiffPayload);
          this.removeHandler(requestId, handler);
          break;
        case 'error':
          onError(message.payload as unknown as ErrorResponse);
          this.removeHandler(requestId, handler);
          break;
      }
    };

    this.addHandler(requestId, handler);

    await this.send({
      type: 'intent_request',
      payload: request as unknown as Record<string, unknown>,
      timestamp: new Date().toISOString(),
      request_id: requestId,
    });
  }

  /**
   * Apply changes after review.
   */
  async applyChanges(executionId: string): Promise<ExecutionUpdate> {
    const requestId = this.generateRequestId();

    return new Promise((resolve, reject) => {
      const handler: MessageHandler = (message) => {
        if (message.request_id !== requestId) return;

        if (message.type === 'execution_update') {
          resolve(message.payload as unknown as ExecutionUpdate);
        } else if (message.type === 'error') {
          reject(new Error((message.payload as ErrorResponse).error));
        }
        this.removeHandler(requestId, handler);
      };

      this.addHandler(requestId, handler);

      this.send({
        type: 'apply_request',
        payload: {
          execution_id: executionId,
          workspace_id: this.workspaceId,
          user_id: '', // Will be filled by auth
        },
        timestamp: new Date().toISOString(),
        request_id: requestId,
      });
    });
  }

  /**
   * Reject changes after review.
   */
  async rejectChanges(executionId: string, reason: string): Promise<ExecutionUpdate> {
    const requestId = this.generateRequestId();

    return new Promise((resolve, reject) => {
      const handler: MessageHandler = (message) => {
        if (message.request_id !== requestId) return;

        if (message.type === 'execution_update') {
          resolve(message.payload as unknown as ExecutionUpdate);
        } else if (message.type === 'error') {
          reject(new Error((message.payload as ErrorResponse).error));
        }
        this.removeHandler(requestId, handler);
      };

      this.addHandler(requestId, handler);

      this.send({
        type: 'reject_request',
        payload: {
          execution_id: executionId,
          workspace_id: this.workspaceId,
          user_id: '',
          reason,
        },
        timestamp: new Date().toISOString(),
        request_id: requestId,
      });
    });
  }

  /**
   * Register a handler for all messages of a type.
   */
  onMessage(type: string, handler: MessageHandler): void {
    this.addHandler(type, handler);
  }

  // ============================================================
  // Private Methods
  // ============================================================

  private async send(message: WebSocketMessage): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }
    this.ws.send(JSON.stringify(message));
  }

  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as WebSocketMessage;

      // Handle request-specific handlers
      if (message.request_id) {
        const handlers = this.messageHandlers.get(message.request_id) || [];
        handlers.forEach((handler) => handler(message));
      }

      // Handle type-specific handlers
      const typeHandlers = this.messageHandlers.get(message.type) || [];
      typeHandlers.forEach((handler) => handler(message));

    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private handleDisconnect(event: CloseEvent): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      setTimeout(() => {
        this.connect().catch((error) => {
          console.error('Reconnection failed:', error);
        });
      }, delay);
    }
  }

  private startPingInterval(): void {
    this.pingInterval = setInterval(() => {
      this.send({
        type: 'ping',
        payload: {},
        timestamp: new Date().toISOString(),
      }).catch(() => {
        // Ping failed, connection likely dead
      });
    }, 30000);
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private addHandler(key: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(key) || [];
    handlers.push(handler);
    this.messageHandlers.set(key, handlers);
  }

  private removeHandler(key: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(key) || [];
    const index = handlers.indexOf(handler);
    if (index !== -1) {
      handlers.splice(index, 1);
    }
    if (handlers.length === 0) {
      this.messageHandlers.delete(key);
    } else {
      this.messageHandlers.set(key, handlers);
    }
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}


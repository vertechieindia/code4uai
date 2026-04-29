/**
 * Core type definitions for the Code Knowledge Graph.
 */

import { z } from 'zod';

// ============================================================================
// Enums
// ============================================================================

export const LanguageSchema = z.enum([
  'typescript',
  'javascript',
  'python',
  'go',
  'rust',
  'java',
  'kotlin',
  'swift',
  'csharp',
  'cpp',
  'c',
]);
export type Language = z.infer<typeof LanguageSchema>;

export const FrameworkSchema = z.enum([
  // Frontend
  'react',
  'vue',
  'angular',
  'svelte',
  'nextjs',
  'remix',
  // Backend
  'fastapi',
  'django',
  'flask',
  'express',
  'nestjs',
  'spring',
  'gin',
  'actix',
]);
export type Framework = z.infer<typeof FrameworkSchema>;

export const RepoTypeSchema = z.enum([
  'micro-frontend',
  'frontend-monolith',
  'microservice',
  'backend-monolith',
  'shared-library',
  'sdk',
  'infrastructure',
  'documentation',
]);
export type RepoType = z.infer<typeof RepoTypeSchema>;

export const SymbolKindSchema = z.enum([
  'function',
  'class',
  'interface',
  'type',
  'enum',
  'variable',
  'constant',
  'method',
  'property',
  'parameter',
  'module',
  'namespace',
]);
export type SymbolKind = z.infer<typeof SymbolKindSchema>;

export const EndpointMethodSchema = z.enum([
  'GET',
  'POST',
  'PUT',
  'PATCH',
  'DELETE',
  'HEAD',
  'OPTIONS',
]);
export type EndpointMethod = z.infer<typeof EndpointMethodSchema>;

export const SchemaSourceSchema = z.enum([
  'pydantic',
  'typescript',
  'openapi',
  'graphql',
  'protobuf',
  'json-schema',
]);
export type SchemaSource = z.infer<typeof SchemaSourceSchema>;

export const FederationRoleSchema = z.enum([
  'host',
  'remote',
  'bidirectional',
]);
export type FederationRole = z.infer<typeof FederationRoleSchema>;

export const VisibilitySchema = z.enum([
  'public',
  'internal',
  'private',
]);
export type Visibility = z.infer<typeof VisibilitySchema>;

// ============================================================================
// Base Types
// ============================================================================

export const NodeIdSchema = z.string().uuid();
export type NodeId = z.infer<typeof NodeIdSchema>;

export const TimestampSchema = z.string().datetime();
export type Timestamp = z.infer<typeof TimestampSchema>;

export const FilePathSchema = z.string().min(1);
export type FilePath = z.infer<typeof FilePathSchema>;

export const LineRangeSchema = z.object({
  start: z.number().int().positive(),
  end: z.number().int().positive(),
});
export type LineRange = z.infer<typeof LineRangeSchema>;

export const LocationSchema = z.object({
  filePath: FilePathSchema,
  lineRange: LineRangeSchema,
  column: z.number().int().nonnegative().optional(),
});
export type Location = z.infer<typeof LocationSchema>;

export const GitInfoSchema = z.object({
  commitSha: z.string().length(40),
  branch: z.string().optional(),
  tag: z.string().optional(),
  author: z.string().optional(),
  timestamp: TimestampSchema.optional(),
});
export type GitInfo = z.infer<typeof GitInfoSchema>;

// ============================================================================
// Schema Field Type
// ============================================================================

export const SchemaFieldSchema = z.object({
  name: z.string(),
  type: z.string(),
  required: z.boolean().default(true),
  description: z.string().optional(),
  default: z.unknown().optional(),
  constraints: z.record(z.unknown()).optional(),
});
export type SchemaField = z.infer<typeof SchemaFieldSchema>;

// ============================================================================
// Module Federation Config
// ============================================================================

export const FederationConfigSchema = z.object({
  role: FederationRoleSchema,
  name: z.string(),
  exposes: z.record(z.string()).optional(),
  remotes: z.record(z.string()).optional(),
  shared: z.array(z.string()).optional(),
});
export type FederationConfig = z.infer<typeof FederationConfigSchema>;


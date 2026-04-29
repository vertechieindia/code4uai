/**
 * Node definitions for the Code Knowledge Graph.
 */

import { z } from 'zod';
import {
  NodeIdSchema,
  TimestampSchema,
  FilePathSchema,
  LocationSchema,
  GitInfoSchema,
  LanguageSchema,
  FrameworkSchema,
  RepoTypeSchema,
  SymbolKindSchema,
  EndpointMethodSchema,
  SchemaSourceSchema,
  SchemaFieldSchema,
  FederationConfigSchema,
  VisibilitySchema,
} from './types.js';

const BaseNodeSchema = z.object({
  id: NodeIdSchema,
  createdAt: TimestampSchema,
  updatedAt: TimestampSchema,
  gitInfo: GitInfoSchema.optional(),
});

export const RepositoryNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('repository'),
  name: z.string().min(1),
  url: z.string().url(),
  repoType: RepoTypeSchema,
  primaryLanguage: LanguageSchema,
  framework: FrameworkSchema.optional(),
  federationConfig: FederationConfigSchema.optional(),
  description: z.string().optional(),
  defaultBranch: z.string().default('main'),
});
export type RepositoryNode = z.infer<typeof RepositoryNodeSchema>;

export const PackageNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('package'),
  name: z.string().min(1),
  version: z.string(),
  repositoryId: NodeIdSchema,
  path: FilePathSchema,
  isPublic: z.boolean().default(false),
  exports: z.array(z.string()).default([]),
  dependencies: z.record(z.string()).default({}),
  devDependencies: z.record(z.string()).default({}),
});
export type PackageNode = z.infer<typeof PackageNodeSchema>;

export const ModuleNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('module'),
  path: FilePathSchema,
  packageId: NodeIdSchema,
  language: LanguageSchema,
  exports: z.array(z.string()).default([]),
  imports: z.array(z.object({
    source: z.string(),
    specifiers: z.array(z.string()),
    isTypeOnly: z.boolean().default(false),
  })).default([]),
  linesOfCode: z.number().int().nonnegative(),
  complexity: z.number().nonnegative().optional(),
});
export type ModuleNode = z.infer<typeof ModuleNodeSchema>;

export const SymbolNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('symbol'),
  name: z.string().min(1),
  kind: SymbolKindSchema,
  moduleId: NodeIdSchema,
  location: LocationSchema,
  signature: z.string().optional(),
  documentation: z.string().optional(),
  visibility: VisibilitySchema.default('public'),
  isAsync: z.boolean().default(false),
  isGenerator: z.boolean().default(false),
  decorators: z.array(z.string()).default([]),
  typeParameters: z.array(z.string()).default([]),
  parameters: z.array(z.object({
    name: z.string(),
    type: z.string().optional(),
    required: z.boolean().default(true),
    defaultValue: z.string().optional(),
  })).default([]),
  returnType: z.string().optional(),
});
export type SymbolNode = z.infer<typeof SymbolNodeSchema>;

export const ServiceNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('service'),
  name: z.string().min(1),
  repositoryId: NodeIdSchema,
  framework: FrameworkSchema,
  basePath: z.string().default('/'),
  version: z.string().optional(),
  description: z.string().optional(),
  healthEndpoint: z.string().optional(),
  dependencies: z.array(z.string()).default([]),
  asyncPatterns: z.array(z.enum(['event-driven', 'saga', 'cqrs', 'polling'])).default([]),
});
export type ServiceNode = z.infer<typeof ServiceNodeSchema>;

export const EndpointNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('endpoint'),
  serviceId: NodeIdSchema,
  path: z.string().min(1),
  method: EndpointMethodSchema,
  operationId: z.string().optional(),
  summary: z.string().optional(),
  description: z.string().optional(),
  requestSchemaId: NodeIdSchema.optional(),
  responseSchemaId: NodeIdSchema.optional(),
  pathParameters: z.array(z.object({
    name: z.string(),
    type: z.string(),
    required: z.boolean().default(true),
  })).default([]),
  queryParameters: z.array(z.object({
    name: z.string(),
    type: z.string(),
    required: z.boolean().default(false),
  })).default([]),
  authentication: z.enum(['none', 'api_key', 'bearer', 'oauth2', 'basic']).default('bearer'),
  rateLimit: z.object({
    requests: z.number(),
    period: z.string(),
  }).optional(),
  deprecated: z.boolean().default(false),
  deprecationMessage: z.string().optional(),
});
export type EndpointNode = z.infer<typeof EndpointNodeSchema>;

export const SchemaNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('schema'),
  name: z.string().min(1),
  source: SchemaSourceSchema,
  language: LanguageSchema,
  moduleId: NodeIdSchema.optional(),
  location: LocationSchema.optional(),
  version: z.string().optional(),
  description: z.string().optional(),
  fields: z.array(SchemaFieldSchema).default([]),
  baseSchemas: z.array(NodeIdSchema).default([]),
  discriminator: z.string().optional(),
  examples: z.array(z.unknown()).default([]),
});
export type SchemaNode = z.infer<typeof SchemaNodeSchema>;

export const TeamNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('team'),
  name: z.string().min(1),
  slug: z.string().regex(/^[a-z0-9-]+$/),
  description: z.string().optional(),
  email: z.string().email().optional(),
  slackChannel: z.string().optional(),
  oncallRotation: z.string().optional(),
  members: z.array(z.object({
    userId: z.string(),
    role: z.enum(['lead', 'member', 'reviewer']),
  })).default([]),
});
export type TeamNode = z.infer<typeof TeamNodeSchema>;

export const OwnershipNodeSchema = BaseNodeSchema.extend({
  nodeType: z.literal('ownership'),
  repositoryId: NodeIdSchema,
  pattern: z.string().min(1),
  teamIds: z.array(NodeIdSchema),
  priority: z.number().int().default(0),
});
export type OwnershipNode = z.infer<typeof OwnershipNodeSchema>;

export const GraphNodeSchema = z.discriminatedUnion('nodeType', [
  RepositoryNodeSchema,
  PackageNodeSchema,
  ModuleNodeSchema,
  SymbolNodeSchema,
  ServiceNodeSchema,
  EndpointNodeSchema,
  SchemaNodeSchema,
  TeamNodeSchema,
  OwnershipNodeSchema,
]);
export type GraphNode = z.infer<typeof GraphNodeSchema>;

export const NodeTypeSchema = z.enum([
  'repository',
  'package',
  'module',
  'symbol',
  'service',
  'endpoint',
  'schema',
  'team',
  'ownership',
]);
export type NodeType = z.infer<typeof NodeTypeSchema>;


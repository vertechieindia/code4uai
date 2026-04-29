/**
 * Relationship definitions for the Code Knowledge Graph.
 */

import { z } from 'zod';
import { NodeIdSchema, TimestampSchema, GitInfoSchema } from './types.js';

export const RelationshipTypeSchema = z.enum([
  'CONTAINS', 'DECLARES', 'EXPOSES',
  'IMPORTS', 'DEPENDS_ON', 'USES', 'IMPLEMENTS', 'EXTENDS', 'REFERENCES',
  'FEDERATES', 'SHARES',
  'OWNS', 'REVIEWS',
  'CONSUMES', 'CALLS', 'EMITS', 'HANDLES',
  'MODIFIED_BY', 'IMPACTS',
]);
export type RelationshipType = z.infer<typeof RelationshipTypeSchema>;

const BaseRelationshipSchema = z.object({
  id: NodeIdSchema,
  sourceId: NodeIdSchema,
  targetId: NodeIdSchema,
  createdAt: TimestampSchema,
  updatedAt: TimestampSchema,
  gitInfo: GitInfoSchema.optional(),
  metadata: z.record(z.unknown()).optional(),
});

export const ContainsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('CONTAINS') });
export const DeclaresRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('DECLARES'), isExported: z.boolean().default(false), isDefault: z.boolean().default(false) });
export const ExposesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('EXPOSES'), exposedAs: z.string().optional(), isPublicApi: z.boolean().default(true) });
export const ImportsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('IMPORTS'), specifiers: z.array(z.string()).default([]), isTypeOnly: z.boolean().default(false), isDynamic: z.boolean().default(false) });
export const DependsOnRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('DEPENDS_ON'), versionConstraint: z.string().optional(), isDev: z.boolean().default(false), isPeer: z.boolean().default(false) });
export const UsesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('USES'), usageCount: z.number().int().positive().default(1), usageLocations: z.array(z.object({ filePath: z.string(), line: z.number() })).default([]) });
export const ImplementsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('IMPLEMENTS') });
export const ExtendsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('EXTENDS') });
export const ReferencesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('REFERENCES'), fieldName: z.string().optional(), isArray: z.boolean().default(false), isOptional: z.boolean().default(false) });
export const FederatesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('FEDERATES'), remoteName: z.string(), exposedModules: z.array(z.string()).default([]), sharedDependencies: z.array(z.string()).default([]) });
export const SharesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('SHARES'), singleton: z.boolean().default(false), requiredVersion: z.string().optional() });
export const OwnsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('OWNS'), pattern: z.string().optional(), isApprover: z.boolean().default(true) });
export const ReviewsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('REVIEWS'), pattern: z.string().optional(), isOptional: z.boolean().default(false) });
export const ConsumesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('CONSUMES'), clientLocation: z.object({ filePath: z.string(), line: z.number() }).optional() });
export const CallsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('CALLS'), isAsync: z.boolean().default(true), timeout: z.number().optional() });
export const EmitsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('EMITS'), eventName: z.string(), eventSchemaId: NodeIdSchema.optional(), isAsync: z.boolean().default(true) });
export const HandlesRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('HANDLES'), eventName: z.string(), handlerLocation: z.object({ filePath: z.string(), line: z.number() }).optional() });
export const ModifiedByRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('MODIFIED_BY'), commitSha: z.string(), author: z.string(), message: z.string().optional(), timestamp: TimestampSchema });
export const ImpactsRelationshipSchema = BaseRelationshipSchema.extend({ type: z.literal('IMPACTS'), impactType: z.enum(['direct', 'indirect', 'potential']), confidence: z.number().min(0).max(1), reason: z.string().optional() });

export const GraphRelationshipSchema = z.discriminatedUnion('type', [
  ContainsRelationshipSchema, DeclaresRelationshipSchema, ExposesRelationshipSchema,
  ImportsRelationshipSchema, DependsOnRelationshipSchema, UsesRelationshipSchema,
  ImplementsRelationshipSchema, ExtendsRelationshipSchema, ReferencesRelationshipSchema,
  FederatesRelationshipSchema, SharesRelationshipSchema,
  OwnsRelationshipSchema, ReviewsRelationshipSchema,
  ConsumesRelationshipSchema, CallsRelationshipSchema, EmitsRelationshipSchema, HandlesRelationshipSchema,
  ModifiedByRelationshipSchema, ImpactsRelationshipSchema,
]);
export type GraphRelationship = z.infer<typeof GraphRelationshipSchema>;


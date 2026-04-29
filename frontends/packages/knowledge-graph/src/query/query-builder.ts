/**
 * Fluent query builder for the Code Knowledge Graph.
 */

import type { KnowledgeGraph } from '../graph/knowledge-graph.js';
import type { GraphNode, NodeType } from '../schema/nodes.js';
import type { RelationshipType, GraphRelationship } from '../schema/relationships.js';
import type { NodeId } from '../schema/types.js';

export interface QueryStep { type: 'filter' | 'traverse' | 'limit' | 'sort'; params: Record<string, unknown>; }
export interface QueryResult<T = GraphNode> { items: T[]; totalCount: number; executionTimeMs: number; }

export class QueryBuilder {
  private steps: QueryStep[] = [];
  private startNodes: NodeId[] = [];
  private startType?: NodeType;

  constructor(private graph: KnowledgeGraph) {}

  from(nodeType: NodeType): this { this.startType = nodeType; return this; }
  fromNodes(...nodeIds: NodeId[]): this { this.startNodes = nodeIds; return this; }
  where(predicate: (node: GraphNode) => boolean): this { this.steps.push({ type: 'filter', params: { predicate } }); return this; }
  whereName(name: string): this { return this.where(node => 'name' in node && node.name === name); }
  whereNameMatches(pattern: RegExp): this { return this.where(node => 'name' in node && typeof node.name === 'string' && pattern.test(node.name)); }
  outgoing(relationshipType?: RelationshipType): this { this.steps.push({ type: 'traverse', params: { direction: 'outgoing', relationshipType } }); return this; }
  incoming(relationshipType?: RelationshipType): this { this.steps.push({ type: 'traverse', params: { direction: 'incoming', relationshipType } }); return this; }
  limit(count: number): this { this.steps.push({ type: 'limit', params: { count } }); return this; }
  sortBy(field: string, direction: 'asc' | 'desc' = 'asc'): this { this.steps.push({ type: 'sort', params: { field, direction } }); return this; }

  execute(): QueryResult {
    const startTime = performance.now();
    let nodes: GraphNode[] = this.startNodes.length > 0 ? this.startNodes.map(id => this.graph.getNode(id)).filter((n): n is GraphNode => n !== undefined) : this.startType ? this.graph.getNodesByType(this.startType) : [];
    let limitCount = Infinity;
    for (const step of this.steps) {
      if (step.type === 'filter') nodes = nodes.filter(step.params.predicate as (node: GraphNode) => boolean);
      if (step.type === 'limit' && step.params.count) limitCount = step.params.count as number;
    }
    const totalCount = nodes.length;
    nodes = nodes.slice(0, limitCount);
    return { items: nodes, totalCount, executionTimeMs: performance.now() - startTime };
  }

  first(): GraphNode | undefined { return this.limit(1).execute().items[0]; }
  count(): number { return this.execute().totalCount; }
  exists(): boolean { return this.count() > 0; }
}

export function query(graph: KnowledgeGraph): QueryBuilder { return new QueryBuilder(graph); }


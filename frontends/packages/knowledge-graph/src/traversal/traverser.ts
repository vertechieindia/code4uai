/**
 * Graph traversal utilities for the Code Knowledge Graph.
 */

import type { KnowledgeGraph } from '../graph/knowledge-graph.js';
import type { GraphNode } from '../schema/nodes.js';
import type { GraphRelationship, RelationshipType } from '../schema/relationships.js';
import type { NodeId } from '../schema/types.js';

export type TraversalDirection = 'outgoing' | 'incoming' | 'both';
export interface TraversalOptions { maxDepth: number; direction: TraversalDirection; relationshipTypes: RelationshipType[]; stopCondition?: (node: GraphNode, depth: number) => boolean; nodeFilter?: (node: GraphNode) => boolean; }
export interface TraversalPath { nodes: GraphNode[]; relationships: GraphRelationship[]; depth: number; }
export interface TraversalResult { visited: GraphNode[]; paths: TraversalPath[]; maxDepthReached: boolean; }

const DEFAULT_OPTIONS: TraversalOptions = { maxDepth: 10, direction: 'outgoing', relationshipTypes: [] };

export class GraphTraverser {
  constructor(private graph: KnowledgeGraph) {}

  bfs(startNodeId: NodeId, options: Partial<TraversalOptions> = {}): TraversalResult {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    const visited = new Map<NodeId, GraphNode>();
    const paths: TraversalPath[] = [];
    let maxDepthReached = false;
    const startNode = this.graph.getNode(startNodeId);
    if (!startNode) return { visited: [], paths: [], maxDepthReached: false };
    visited.set(startNodeId, startNode);
    const queue: { nodeId: NodeId; depth: number; path: TraversalPath }[] = [{ nodeId: startNodeId, depth: 0, path: { nodes: [startNode], relationships: [], depth: 0 } }];
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current.depth >= opts.maxDepth) { maxDepthReached = true; paths.push(current.path); continue; }
      const currentNode = this.graph.getNode(current.nodeId);
      if (!currentNode) continue;
      if (opts.stopCondition?.(currentNode, current.depth)) { paths.push(current.path); continue; }
      const relationships = this.getRelationships(current.nodeId, opts);
      let hasNext = false;
      for (const rel of relationships) {
        const nextNodeId = opts.direction === 'incoming' ? rel.sourceId : rel.targetId;
        if (visited.has(nextNodeId)) continue;
        const nextNode = this.graph.getNode(nextNodeId);
        if (!nextNode) continue;
        if (opts.nodeFilter && !opts.nodeFilter(nextNode)) continue;
        visited.set(nextNodeId, nextNode);
        hasNext = true;
        queue.push({ nodeId: nextNodeId, depth: current.depth + 1, path: { nodes: [...current.path.nodes, nextNode], relationships: [...current.path.relationships, rel], depth: current.depth + 1 } });
      }
      if (!hasNext) paths.push(current.path);
    }
    return { visited: Array.from(visited.values()), paths, maxDepthReached };
  }

  findShortestPath(startNodeId: NodeId, endNodeId: NodeId, options: Partial<TraversalOptions> = {}): TraversalPath | null {
    const opts = { ...DEFAULT_OPTIONS, ...options, direction: 'both' as TraversalDirection };
    const result = this.bfs(startNodeId, { ...opts, stopCondition: (node) => node.id === endNodeId });
    for (const path of result.paths) {
      const lastNode = path.nodes[path.nodes.length - 1];
      if (lastNode && lastNode.id === endNodeId) return path;
    }
    return null;
  }

  private getRelationships(nodeId: NodeId, opts: TraversalOptions): GraphRelationship[] {
    let rels: GraphRelationship[] = [];
    if (opts.direction === 'outgoing' || opts.direction === 'both') rels.push(...this.graph.getOutgoingRelationships(nodeId));
    if (opts.direction === 'incoming' || opts.direction === 'both') rels.push(...this.graph.getIncomingRelationships(nodeId));
    if (opts.relationshipTypes.length > 0) rels = rels.filter(r => opts.relationshipTypes.includes(r.type));
    return rels;
  }
}


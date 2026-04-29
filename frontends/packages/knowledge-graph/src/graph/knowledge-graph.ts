/**
 * Core Knowledge Graph implementation.
 */

import type { GraphNode, NodeType } from '../schema/nodes.js';
import type { GraphRelationship, RelationshipType } from '../schema/relationships.js';
import type { NodeId } from '../schema/types.js';

export interface GraphStats {
  nodeCount: number;
  relationshipCount: number;
  nodesByType: Record<NodeType, number>;
  relationshipsByType: Record<RelationshipType, number>;
}

export interface NodeQuery {
  nodeType?: NodeType;
  repositoryId?: NodeId;
  packageId?: NodeId;
  moduleId?: NodeId;
  name?: string;
  pattern?: RegExp;
}

export interface RelationshipQuery {
  type?: RelationshipType;
  sourceId?: NodeId;
  targetId?: NodeId;
  sourceType?: NodeType;
  targetType?: NodeType;
}

export class KnowledgeGraph {
  private nodes: Map<NodeId, GraphNode> = new Map();
  private relationships: Map<NodeId, GraphRelationship> = new Map();
  private nodesByType: Map<NodeType, Set<NodeId>> = new Map();
  private outgoingRelationships: Map<NodeId, Set<NodeId>> = new Map();
  private incomingRelationships: Map<NodeId, Set<NodeId>> = new Map();
  private relationshipsByType: Map<RelationshipType, Set<NodeId>> = new Map();

  constructor() {
    const nodeTypes: NodeType[] = ['repository', 'package', 'module', 'symbol', 'service', 'endpoint', 'schema', 'team', 'ownership'];
    for (const type of nodeTypes) {
      this.nodesByType.set(type, new Set());
    }
  }

  addNode(node: GraphNode): void {
    if (this.nodes.has(node.id)) throw new Error(`Node ${node.id} already exists`);
    this.nodes.set(node.id, node);
    this.nodesByType.get(node.nodeType)?.add(node.id);
    this.outgoingRelationships.set(node.id, new Set());
    this.incomingRelationships.set(node.id, new Set());
  }

  updateNode(nodeId: NodeId, updates: Partial<GraphNode>): GraphNode {
    const existing = this.nodes.get(nodeId);
    if (!existing) throw new Error(`Node ${nodeId} not found`);
    const updated = { ...existing, ...updates, id: existing.id, nodeType: existing.nodeType, updatedAt: new Date().toISOString() } as GraphNode;
    this.nodes.set(nodeId, updated);
    return updated;
  }

  removeNode(nodeId: NodeId): void {
    const node = this.nodes.get(nodeId);
    if (!node) return;
    const outgoing = this.outgoingRelationships.get(nodeId) ?? new Set();
    const incoming = this.incomingRelationships.get(nodeId) ?? new Set();
    for (const relId of [...outgoing, ...incoming]) this.removeRelationship(relId);
    this.nodesByType.get(node.nodeType)?.delete(nodeId);
    this.outgoingRelationships.delete(nodeId);
    this.incomingRelationships.delete(nodeId);
    this.nodes.delete(nodeId);
  }

  getNode(nodeId: NodeId): GraphNode | undefined { return this.nodes.get(nodeId); }
  getNodeAs<T extends GraphNode>(nodeId: NodeId): T | undefined { return this.nodes.get(nodeId) as T | undefined; }
  hasNode(nodeId: NodeId): boolean { return this.nodes.has(nodeId); }

  getNodesByType<T extends GraphNode>(nodeType: NodeType): T[] {
    const ids = this.nodesByType.get(nodeType) ?? new Set();
    return Array.from(ids).map(id => this.nodes.get(id)).filter((n): n is T => n !== undefined);
  }

  queryNodes(query: NodeQuery): GraphNode[] {
    let candidates = query.nodeType ? this.getNodesByType(query.nodeType) : Array.from(this.nodes.values());
    return candidates.filter(node => {
      if (query.name && !('name' in node && node.name === query.name)) return false;
      if (query.pattern && !('name' in node && typeof node.name === 'string' && query.pattern.test(node.name))) return false;
      return true;
    });
  }

  addRelationship(relationship: GraphRelationship): void {
    if (this.relationships.has(relationship.id)) throw new Error(`Relationship ${relationship.id} already exists`);
    if (!this.nodes.has(relationship.sourceId)) throw new Error(`Source node ${relationship.sourceId} not found`);
    if (!this.nodes.has(relationship.targetId)) throw new Error(`Target node ${relationship.targetId} not found`);
    this.relationships.set(relationship.id, relationship);
    this.outgoingRelationships.get(relationship.sourceId)?.add(relationship.id);
    this.incomingRelationships.get(relationship.targetId)?.add(relationship.id);
    if (!this.relationshipsByType.has(relationship.type)) this.relationshipsByType.set(relationship.type, new Set());
    this.relationshipsByType.get(relationship.type)?.add(relationship.id);
  }

  removeRelationship(relationshipId: NodeId): void {
    const rel = this.relationships.get(relationshipId);
    if (!rel) return;
    this.outgoingRelationships.get(rel.sourceId)?.delete(relationshipId);
    this.incomingRelationships.get(rel.targetId)?.delete(relationshipId);
    this.relationshipsByType.get(rel.type)?.delete(relationshipId);
    this.relationships.delete(relationshipId);
  }

  getRelationship(relationshipId: NodeId): GraphRelationship | undefined { return this.relationships.get(relationshipId); }

  getOutgoingRelationships(nodeId: NodeId, type?: RelationshipType): GraphRelationship[] {
    const relIds = this.outgoingRelationships.get(nodeId) ?? new Set();
    return Array.from(relIds).map(id => this.relationships.get(id)).filter((r): r is GraphRelationship => r !== undefined).filter(r => !type || r.type === type);
  }

  getIncomingRelationships(nodeId: NodeId, type?: RelationshipType): GraphRelationship[] {
    const relIds = this.incomingRelationships.get(nodeId) ?? new Set();
    return Array.from(relIds).map(id => this.relationships.get(id)).filter((r): r is GraphRelationship => r !== undefined).filter(r => !type || r.type === type);
  }

  getStats(): GraphStats {
    const nodesByType: Record<string, number> = {};
    for (const [type, ids] of this.nodesByType) nodesByType[type] = ids.size;
    const relationshipsByType: Record<string, number> = {};
    for (const [type, ids] of this.relationshipsByType) relationshipsByType[type] = ids.size;
    return { nodeCount: this.nodes.size, relationshipCount: this.relationships.size, nodesByType: nodesByType as Record<NodeType, number>, relationshipsByType: relationshipsByType as Record<RelationshipType, number> };
  }

  toJSON(): { nodes: GraphNode[]; relationships: GraphRelationship[] } {
    return { nodes: Array.from(this.nodes.values()), relationships: Array.from(this.relationships.values()) };
  }

  static fromJSON(data: { nodes: GraphNode[]; relationships: GraphRelationship[] }): KnowledgeGraph {
    const graph = new KnowledgeGraph();
    for (const node of data.nodes) graph.addNode(node);
    for (const rel of data.relationships) graph.addRelationship(rel);
    return graph;
  }
}


/**
 * High-level graph operations for code4u.ai.
 */

import type { KnowledgeGraph } from './knowledge-graph.js';
import type { GraphNode, SymbolNode, TeamNode, ModuleNode, EndpointNode, SchemaNode, RepositoryNode } from '../schema/nodes.js';
import type { GraphRelationship } from '../schema/relationships.js';
import type { NodeId } from '../schema/types.js';

export interface OwnershipInfo { teams: TeamNode[]; primaryTeam?: TeamNode; patterns: string[]; }
export interface DependencyInfo { directDependencies: GraphNode[]; transitiveDependencies: GraphNode[]; dependents: GraphNode[]; depth: number; }
export interface ImpactAnalysis { directlyAffected: GraphNode[]; transitivelyAffected: GraphNode[]; owners: TeamNode[]; breakingChange: boolean; blastRadius: { repositories: number; packages: number; modules: number; symbols: number; services: number; endpoints: number; teams: number; }; }
export interface CrossRepoLink { sourceRepo: RepositoryNode; targetRepo: RepositoryNode; linkType: 'dependency' | 'federation' | 'api_consumption'; strength: number; }

export class GraphOperations {
  constructor(private graph: KnowledgeGraph) {}

  findSymbol(qualifiedName: string): SymbolNode | undefined {
    const parts = qualifiedName.split('.');
    const symbolName = parts.pop();
    if (!symbolName) return undefined;
    const symbols = this.graph.getNodesByType<SymbolNode>('symbol');
    return symbols.find(s => s.name === symbolName);
  }

  findSymbolUsages(symbolId: NodeId): { node: GraphNode; relationship: GraphRelationship }[] {
    const usages = this.graph.getIncomingRelationships(symbolId, 'USES');
    return usages.map(rel => ({ node: this.graph.getNode(rel.sourceId)!, relationship: rel })).filter(u => u.node !== undefined);
  }

  getOwnership(nodeId: NodeId): OwnershipInfo {
    const ownershipRels = this.graph.getIncomingRelationships(nodeId, 'OWNS');
    const teams: TeamNode[] = [];
    const patterns: string[] = [];
    for (const rel of ownershipRels) {
      const team = this.graph.getNodeAs<TeamNode>(rel.sourceId);
      if (team) teams.push(team);
    }
    return { teams, primaryTeam: teams[0], patterns };
  }

  getDependencies(nodeId: NodeId, maxDepth: number = 5): DependencyInfo {
    const directDeps = this.getDirectDependencies(nodeId);
    const transitiveDeps = this.getTransitiveDependencies(nodeId, maxDepth);
    const dependents = this.getDependents(nodeId);
    return { directDependencies: directDeps, transitiveDependencies: transitiveDeps, dependents, depth: maxDepth };
  }

  private getDirectDependencies(nodeId: NodeId): GraphNode[] {
    const depRels = this.graph.getOutgoingRelationships(nodeId);
    const depTypes = ['IMPORTS', 'DEPENDS_ON', 'USES', 'CALLS', 'CONSUMES'];
    return depRels.filter(rel => depTypes.includes(rel.type)).map(rel => this.graph.getNode(rel.targetId)).filter((n): n is GraphNode => n !== undefined);
  }

  private getTransitiveDependencies(nodeId: NodeId, maxDepth: number): GraphNode[] {
    const visited = new Set<NodeId>([nodeId]);
    const result: GraphNode[] = [];
    let currentLevel = [nodeId];
    for (let depth = 0; depth < maxDepth && currentLevel.length > 0; depth++) {
      const nextLevel: NodeId[] = [];
      for (const id of currentLevel) {
        const deps = this.getDirectDependencies(id);
        for (const dep of deps) {
          if (!visited.has(dep.id)) { visited.add(dep.id); result.push(dep); nextLevel.push(dep.id); }
        }
      }
      currentLevel = nextLevel;
    }
    return result;
  }

  private getDependents(nodeId: NodeId): GraphNode[] {
    const depRels = this.graph.getIncomingRelationships(nodeId);
    const depTypes = ['IMPORTS', 'DEPENDS_ON', 'USES', 'CALLS', 'CONSUMES'];
    return depRels.filter(rel => depTypes.includes(rel.type)).map(rel => this.graph.getNode(rel.sourceId)).filter((n): n is GraphNode => n !== undefined);
  }

  analyzeImpact(nodeId: NodeId, changeType: 'modify' | 'delete' | 'rename'): ImpactAnalysis {
    const node = this.graph.getNode(nodeId);
    if (!node) throw new Error(`Node ${nodeId} not found`);
    const directlyAffected = this.getDependents(nodeId);
    const transitivelyAffected = this.getTransitiveImpact(nodeId, new Set([nodeId]));
    const ownerSet = new Set<NodeId>();
    const allAffected = [...directlyAffected, ...transitivelyAffected, node];
    for (const affected of allAffected) {
      const ownership = this.getOwnership(affected.id);
      for (const team of ownership.teams) ownerSet.add(team.id);
    }
    const owners = Array.from(ownerSet).map(id => this.graph.getNodeAs<TeamNode>(id)).filter((t): t is TeamNode => t !== undefined);
    const blastRadius = this.calculateBlastRadius(allAffected);
    const breakingChange = this.isBreakingChange(node, changeType, directlyAffected);
    return { directlyAffected, transitivelyAffected, owners, breakingChange, blastRadius };
  }

  private getTransitiveImpact(nodeId: NodeId, visited: Set<NodeId>): GraphNode[] {
    const result: GraphNode[] = [];
    const directDependents = this.getDependents(nodeId);
    for (const dep of directDependents) {
      if (!visited.has(dep.id)) { visited.add(dep.id); result.push(dep); result.push(...this.getTransitiveImpact(dep.id, visited)); }
    }
    return result;
  }

  private calculateBlastRadius(affected: GraphNode[]): ImpactAnalysis['blastRadius'] {
    const repos = new Set<NodeId>(), packages = new Set<NodeId>(), modules = new Set<NodeId>(), symbols = new Set<NodeId>(), services = new Set<NodeId>(), endpoints = new Set<NodeId>(), teams = new Set<NodeId>();
    for (const node of affected) {
      if (node.nodeType === 'repository') repos.add(node.id);
      if (node.nodeType === 'package') { packages.add(node.id); repos.add(node.repositoryId); }
      if (node.nodeType === 'module') { modules.add(node.id); packages.add(node.packageId); }
      if (node.nodeType === 'symbol') { symbols.add(node.id); modules.add(node.moduleId); }
      if (node.nodeType === 'service') { services.add(node.id); repos.add(node.repositoryId); }
      if (node.nodeType === 'endpoint') { endpoints.add(node.id); services.add(node.serviceId); }
      const ownership = this.getOwnership(node.id);
      for (const team of ownership.teams) teams.add(team.id);
    }
    return { repositories: repos.size, packages: packages.size, modules: modules.size, symbols: symbols.size, services: services.size, endpoints: endpoints.size, teams: teams.size };
  }

  private isBreakingChange(node: GraphNode, changeType: string, dependents: GraphNode[]): boolean {
    if ((changeType === 'delete' || changeType === 'rename') && dependents.length > 0) return true;
    if (node.nodeType === 'schema' || node.nodeType === 'endpoint') return dependents.length > 0;
    return false;
  }

  findEndpointConsumers(endpointId: NodeId): ModuleNode[] {
    const consumeRels = this.graph.getIncomingRelationships(endpointId, 'CONSUMES');
    return consumeRels.map(rel => this.graph.getNodeAs<ModuleNode>(rel.sourceId)).filter((m): m is ModuleNode => m !== undefined);
  }

  findSchemaUsages(schemaId: NodeId): { endpoints: EndpointNode[]; symbols: SymbolNode[]; schemas: SchemaNode[] } {
    const endpoints: EndpointNode[] = [], symbols: SymbolNode[] = [], schemas: SchemaNode[] = [];
    const usesRels = this.graph.getIncomingRelationships(schemaId, 'USES');
    for (const rel of usesRels) {
      const endpoint = this.graph.getNodeAs<EndpointNode>(rel.sourceId);
      if (endpoint) endpoints.push(endpoint);
      const symbol = this.graph.getNodeAs<SymbolNode>(rel.sourceId);
      if (symbol) symbols.push(symbol);
    }
    const refRels = this.graph.getIncomingRelationships(schemaId, 'REFERENCES');
    for (const rel of refRels) {
      const schema = this.graph.getNodeAs<SchemaNode>(rel.sourceId);
      if (schema) schemas.push(schema);
    }
    return { endpoints, symbols, schemas };
  }
}


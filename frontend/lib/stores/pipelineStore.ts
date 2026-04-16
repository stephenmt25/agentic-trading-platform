import { create } from "zustand";
import type { Node, Edge } from "@xyflow/react";

interface PipelineState {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  profileId: string | null;
  isDirty: boolean;
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: Node[]) => void;
  onEdgesChange: (changes: Edge[]) => void;
  setSelectedNodeId: (id: string | null) => void;
  setProfileId: (id: string) => void;
  markDirty: () => void;
  markClean: () => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  profileId: null,
  isDirty: false,
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  onNodesChange: (nodes) => set({ nodes, isDirty: true }),
  onEdgesChange: (edges) => set({ edges, isDirty: true }),
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setProfileId: (id) => set({ profileId: id }),
  markDirty: () => set({ isDirty: true }),
  markClean: () => set({ isDirty: false }),
}));

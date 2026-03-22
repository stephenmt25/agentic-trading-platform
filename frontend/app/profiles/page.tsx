"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Save, Plus, Activity, Power, PowerOff, Code, Loader2, Trash2, X, Copy, Ban } from "lucide-react";
import { toast } from "sonner";
import { api, type ProfileResponse } from "@/lib/api/client";

const DEFAULT_RULES = {
  strategy: "momentum",
  symbols: ["BTC/USDT"],
  timeframe: "1h",
  entry_conditions: {
    rsi_below: 30,
    volume_spike: true,
  },
  exit_conditions: {
    rsi_above: 70,
    trailing_stop_pct: 2.0,
  },
};

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<ProfileResponse[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Create profile modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileAllocation, setNewProfileAllocation] = useState("1.0");
  const [isCreating, setIsCreating] = useState(false);

  // Delete state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const searchParams = useSearchParams();

  useEffect(() => {
    loadProfiles();
  }, []);

  const loadProfiles = async () => {
    setIsLoading(true);
    try {
      const fetched = await api.profiles.list();
      setProfiles(fetched);
      // Check for ?selected= query param from dashboard navigation
      const preselected = searchParams.get("selected");
      if (preselected && fetched.some(p => p.profile_id === preselected)) {
        setSelectedProfileId(preselected);
      } else if (fetched.length > 0 && !selectedProfileId) {
        setSelectedProfileId(fetched[0].profile_id);
      }
    } catch (e: any) {
      if (!e.message?.includes("Unauthorized")) {
        console.error("Failed to load profiles:", e);
        toast.error("Could not load profiles. Is the backend running?");
      }
      setProfiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedProfile = profiles.find(p => p.profile_id === selectedProfileId);

  useEffect(() => {
    if (selectedProfile) {
      setEditorContent(JSON.stringify(selectedProfile.rules_json, null, 2));
    } else {
      setEditorContent("");
    }
  }, [selectedProfileId, selectedProfile]);

  const handleSave = async () => {
    if (!selectedProfile) return;
    setIsSaving(true);
    try {
      const parsed = JSON.parse(editorContent);
      await api.profiles.update(selectedProfile.profile_id, {
        rules_json: parsed,
        is_active: selectedProfile.is_active,
      });
      toast.success("Profile saved!");
      await loadProfiles();
    } catch (e: any) {
      if (e instanceof SyntaxError) {
        toast.error("Invalid JSON format");
      } else {
        toast.error(e.message || "Failed to save profile");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggle = async () => {
    if (!selectedProfile) return;
    try {
      await api.profiles.toggle(selectedProfile.profile_id, !selectedProfile.is_active);
      toast.success(selectedProfile.is_active ? "Profile deactivated" : "Profile activated");
      await loadProfiles();
    } catch (e: any) {
      toast.error(e.message || "Failed to toggle profile");
    }
  };

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) {
      toast.error("Please enter a profile name");
      return;
    }
    setIsCreating(true);
    try {
      const result = await api.profiles.create({
        name: newProfileName.trim(),
        rules_json: DEFAULT_RULES,
        allocation_pct: parseFloat(newProfileAllocation) || 1.0,
      });
      toast.success(`Profile "${newProfileName}" created!`);
      setShowCreateModal(false);
      setNewProfileName("");
      setNewProfileAllocation("1.0");
      await loadProfiles();
      // Select the new profile
      if (result.id) {
        setSelectedProfileId(result.id);
      }
    } catch (e: any) {
      toast.error(e.message || "Failed to create profile");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteProfile = async () => {
    if (!selectedProfile) return;
    setIsDeleting(true);
    try {
      await api.profiles.delete(selectedProfile.profile_id);
      toast.success("Profile archived. JSON is still available to copy.");
      setShowDeleteConfirm(false);
      // Refresh from backend so deleted_at is reflected
      await loadProfiles();
    } catch (e: any) {
      toast.error(e.message || "Failed to delete profile");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCopyJson = () => {
    navigator.clipboard.writeText(editorContent);
    toast.success("JSON copied to clipboard");
  };

  const isSelectedDeleted = selectedProfile ? !!selectedProfile.deleted_at : false;

  const activeCount = profiles.filter(p => p.is_active).length;

  const filteredProfiles = profiles.filter(p =>
    p.profile_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full gap-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border pb-4 gap-3 shrink-0">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground mb-1">Agent Profiles</h1>
          <p className="text-muted-foreground text-sm">Manage trading agent boundaries, logic, and state.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-emerald-500 font-mono tabular-nums">
            {activeCount} active
          </span>
          <Button
            className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium min-h-[44px]"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" /> New Profile
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-[600px] overflow-hidden">
        {/* Left Column: List */}
        <div className="lg:col-span-4 flex flex-col gap-3 overflow-hidden">
          <Input
            type="search"
            placeholder="Search profiles..."
            className="bg-card border-border shrink-0 min-h-[44px]"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="flex flex-col gap-1 overflow-y-auto pr-1 pb-4 flex-1">
            {isLoading ? (
              <div className="flex flex-col gap-2 p-2">
                <div className="h-14 bg-accent animate-pulse rounded-md" />
                <div className="h-14 bg-accent animate-pulse rounded-md" />
                <div className="h-14 bg-accent animate-pulse rounded-md" />
                <div className="h-14 bg-accent animate-pulse rounded-md" />
              </div>
            ) : filteredProfiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 text-center">
                <p className="text-sm text-muted-foreground">
                  {profiles.length === 0
                    ? "No profiles yet. Click \"New Profile\" to create one."
                    : "No profiles match your search."}
                </p>
              </div>
            ) : (
              filteredProfiles.map(p => {
                const isDeleted = !!p.deleted_at;
                return (
                  <button
                    key={p.profile_id}
                    onClick={() => setSelectedProfileId(p.profile_id)}
                    className={`cursor-pointer transition-colors border shrink-0 rounded-md text-left w-full min-h-[44px] ${
                      isDeleted
                        ? 'border-border bg-card/50 opacity-50'
                        : selectedProfileId === p.profile_id
                          ? 'border-primary bg-primary/5'
                          : 'border-transparent hover:bg-accent'
                    }`}
                  >
                    <div className="p-3 flex items-center justify-between relative">
                      {!isDeleted && selectedProfileId === p.profile_id && (
                        <div className="absolute left-0 top-1 bottom-1 w-0.5 bg-primary rounded-full" />
                      )}
                      <div className="flex flex-col gap-0.5 pl-2">
                        <span className={`font-mono font-medium text-sm ${isDeleted ? 'text-muted-foreground line-through' : 'text-foreground'}`}>{p.name || p.profile_id}</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          {isDeleted ? (
                            <><Ban className="w-3 h-3 text-red-500/60" /> <span className="text-red-500/60">Deleted</span></>
                          ) : p.is_active ? (
                            <><Power className="w-3 h-3 text-emerald-500" /> Running</>
                          ) : (
                            <><PowerOff className="w-3 h-3 text-muted-foreground" /> Dormant</>
                          )}
                        </span>
                      </div>
                      <div>
                        {isDeleted ? (
                          <Badge variant="outline" className="text-red-500/60 border-red-500/20 text-xs">DELETED</Badge>
                        ) : p.is_active ? (
                          <span className="inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                        ) : null}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Editor */}
        <div className={`lg:col-span-8 flex flex-col border border-border rounded-md overflow-hidden h-full ${isSelectedDeleted ? 'opacity-70' : ''}`}>
          {selectedProfile ? (
            <>
              <div className={`border-b py-3 px-4 shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${isSelectedDeleted ? 'bg-red-950/10 border-red-500/10' : 'border-border'}`}>
                <div>
                  <h3 className={`text-base font-mono font-medium ${isSelectedDeleted ? 'text-muted-foreground' : 'text-foreground'}`}>
                    {selectedProfile.name || selectedProfile.profile_id}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {isSelectedDeleted ? (
                      <span className="text-red-500/60 font-medium uppercase tracking-wider">Deleted -- JSON retained for reference</span>
                    ) : (
                      'JSON Configuration'
                    )}
                  </p>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {isSelectedDeleted ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCopyJson}
                      className="border-border text-foreground/80 hover:bg-accent min-h-[44px]"
                    >
                      <Copy className="w-4 h-4 mr-2" /> Copy JSON
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-red-500/30 text-red-500 hover:bg-accent min-h-[44px]"
                        onClick={() => setShowDeleteConfirm(true)}
                      >
                        <Trash2 className="w-4 h-4 mr-1" /> Delete
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-border hover:bg-accent text-foreground/80 min-h-[44px]"
                        onClick={handleToggle}
                      >
                        {selectedProfile.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={isSaving}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium min-h-[44px]"
                      >
                        {isSaving ? (
                          <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                        ) : (
                          <><Save className="w-4 h-4 mr-2" /> Save</>
                        )}
                      </Button>
                    </>
                  )}
                </div>
              </div>
              <div className={`flex-1 relative p-4 text-sm overflow-hidden ${isSelectedDeleted ? 'bg-background/50' : 'bg-background'}`}>
                <textarea
                  className={`w-full h-full bg-transparent font-mono tabular-nums resize-none focus:outline-none ${isSelectedDeleted ? 'text-muted-foreground cursor-default' : 'text-foreground/80 placeholder:text-muted-foreground/30'}`}
                  value={editorContent}
                  onChange={(e) => !isSelectedDeleted && setEditorContent(e.target.value)}
                  readOnly={isSelectedDeleted}
                  spellCheck={false}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
              <p className="text-sm">Select a profile to view configuration</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Profile Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-md w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="text-lg font-medium text-foreground">Create New Profile</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" aria-label="Close dialog">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">Profile Name</label>
                <Input
                  type="text"
                  placeholder="e.g. BTC Momentum Scanner"
                  className="bg-background border-border text-foreground min-h-[44px]"
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">Allocation %</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  placeholder="1.0"
                  className="bg-background border-border text-foreground font-mono tabular-nums min-h-[44px]"
                  value={newProfileAllocation}
                  onChange={(e) => setNewProfileAllocation(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">Percentage of portfolio allocated to this agent.</p>
              </div>
              <div className="border-t border-border pt-3">
                <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-1">Strategy Template</p>
                <p className="text-sm text-muted-foreground">A default momentum strategy will be applied. You can edit the JSON rules after creation.</p>
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
              <Button variant="ghost" onClick={() => setShowCreateModal(false)} className="text-muted-foreground min-h-[44px]">
                Cancel
              </Button>
              <Button
                onClick={handleCreateProfile}
                disabled={isCreating || !newProfileName.trim()}
                className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium min-h-[44px]"
              >
                {isCreating ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating...</>
                ) : (
                  <><Plus className="w-4 h-4 mr-2" /> Create Profile</>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && selectedProfile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-md w-full max-w-sm mx-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-5 text-center">
              <h2 className="text-lg font-medium text-foreground mb-2">Delete Profile?</h2>
              <p className="text-sm text-muted-foreground">
                This will permanently deactivate <strong className="text-foreground">{selectedProfile.name || selectedProfile.profile_id}</strong>. This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3 px-6 py-4 border-t border-border">
              <Button variant="ghost" onClick={() => setShowDeleteConfirm(false)} className="flex-1 text-muted-foreground min-h-[44px]">
                Cancel
              </Button>
              <Button
                onClick={handleDeleteProfile}
                disabled={isDeleting}
                className="flex-1 bg-red-600 hover:bg-red-500 text-white font-medium min-h-[44px]"
              >
                {isDeleting ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Deleting...</>
                ) : (
                  "Delete"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

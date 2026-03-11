"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
      console.error("Failed to load profiles:", e);
      toast.error("Could not load profiles. Is the backend running?");
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
      <div className="flex items-center justify-between border-b border-border pb-4 shrink-0">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white mb-1">AGENT PROFILES</h1>
          <p className="text-muted-foreground text-sm">Manage trading agent boundaries, logic, and state.</p>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 px-3 py-1">
            <Activity className="w-3 h-3 mr-2 inline" />
            {activeCount} Active
          </Badge>
          <Button
            className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold tracking-wider"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" /> NEW PROFILE
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1 min-h-[600px] overflow-hidden">
        {/* Left Column: List */}
        <div className="lg:col-span-4 flex flex-col gap-4 overflow-hidden">
          <Input
            type="search"
            placeholder="Search profiles..."
            className="bg-card border-border shrink-0"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="flex flex-col gap-3 overflow-y-auto pr-2 pb-4 flex-1">
            {isLoading ? (
              <div className="flex items-center justify-center p-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredProfiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 text-center">
                <Code className="w-8 h-8 text-muted-foreground mb-3 opacity-30" />
                <p className="text-sm text-muted-foreground">
                  {profiles.length === 0
                    ? "No profiles yet. Click \"NEW PROFILE\" to create one."
                    : "No profiles match your search."}
                </p>
              </div>
            ) : (
              filteredProfiles.map(p => {
                const isDeleted = !!p.deleted_at;
                return (
                  <Card
                    key={p.profile_id}
                    onClick={() => setSelectedProfileId(p.profile_id)}
                    className={`cursor-pointer transition-all border shrink-0 ${
                      isDeleted
                        ? 'border-slate-800 bg-slate-900/30 opacity-50'
                        : selectedProfileId === p.profile_id
                          ? 'border-primary ring-1 ring-primary/50 bg-primary/5'
                          : 'border-border hover:border-slate-600 bg-card hover:bg-slate-900/50'
                    }`}
                  >
                    <div className="p-4 flex items-center justify-between relative overflow-hidden">
                      {!isDeleted && selectedProfileId === p.profile_id && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary" />
                      )}
                      {isDeleted && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500/50" />
                      )}
                      <div className="flex flex-col gap-1">
                        <span className={`font-mono font-bold text-sm ${isDeleted ? 'text-slate-500 line-through' : 'text-slate-200'}`}>{p.name || p.profile_id}</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          {isDeleted ? (
                            <><Ban className="w-3 h-3 text-red-500/60" /> <span className="text-red-500/60">Deleted</span></>
                          ) : p.is_active ? (
                            <><Power className="w-3 h-3 text-emerald-500" /> Running</>
                          ) : (
                            <><PowerOff className="w-3 h-3 text-slate-500" /> Dormant</>
                          )}
                        </span>
                      </div>
                      <div>
                        {isDeleted ? (
                          <Badge variant="outline" className="text-red-500/60 border-red-500/20 bg-red-500/5 text-[10px] font-bold">DELETED</Badge>
                        ) : p.is_active ? (
                          <span className="flex h-2 w-2 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span></span>
                        ) : null}
                      </div>
                    </div>
                  </Card>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Editor */}
        <Card className={`lg:col-span-8 flex flex-col border-border bg-card shadow-xl overflow-hidden h-full ${isSelectedDeleted ? 'opacity-70' : ''}`}>
          {selectedProfile ? (
            <>
              <CardHeader className={`border-b py-4 shrink-0 ${isSelectedDeleted ? 'bg-red-950/20 border-red-500/10' : 'bg-slate-900/50 border-border'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {isSelectedDeleted ? (
                      <Ban className="text-red-500/60 w-5 h-5 flex-shrink-0" />
                    ) : (
                      <Code className="text-primary w-5 h-5 flex-shrink-0" />
                    )}
                    <div>
                      <CardTitle className={`text-lg font-mono font-bold ${isSelectedDeleted ? 'text-slate-500' : 'text-slate-200'}`}>
                        {selectedProfile.name || selectedProfile.profile_id}
                      </CardTitle>
                      <CardDescription className="text-xs">
                        {isSelectedDeleted ? (
                          <span className="text-red-500/60 font-bold uppercase tracking-wider">Deleted — JSON retained for reference</span>
                        ) : (
                          'JSON Configuration'
                        )}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {isSelectedDeleted ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCopyJson}
                        className="border-slate-700 text-slate-300 hover:bg-slate-800"
                      >
                        <Copy className="w-4 h-4 mr-2" /> COPY JSON
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-red-500/30 text-red-400 hover:bg-red-900/20 hover:text-red-300"
                          onClick={() => setShowDeleteConfirm(true)}
                        >
                          <Trash2 className="w-4 h-4 mr-1" /> DELETE
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-border hover:bg-slate-800 text-slate-300"
                          onClick={handleToggle}
                        >
                          {selectedProfile.is_active ? 'DEACTIVATE' : 'ACTIVATE'}
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleSave}
                          disabled={isSaving}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold"
                        >
                          {isSaving ? (
                            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> SAVING...</>
                          ) : (
                            <><Save className="w-4 h-4 mr-2" /> SAVE</>
                          )}
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </CardHeader>
              <div className={`flex-1 relative p-4 text-sm overflow-hidden ${isSelectedDeleted ? 'bg-[#0d1117]/50' : 'bg-[#0d1117]'}`}>
                <textarea
                  className={`w-full h-full bg-transparent font-mono resize-none focus:outline-none font-medium ${isSelectedDeleted ? 'text-slate-600 cursor-default' : 'text-slate-300 placeholder:text-slate-700'}`}
                  value={editorContent}
                  onChange={(e) => !isSelectedDeleted && setEditorContent(e.target.value)}
                  readOnly={isSelectedDeleted}
                  spellCheck={false}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-4">
              <Code className="w-12 h-12 opacity-20" />
              <p>Select a profile to view configuration</p>
            </div>
          )}
        </Card>
      </div>

      {/* Create Profile Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
              <h2 className="text-lg font-bold text-white">Create New Profile</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-500 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Profile Name</label>
                <Input
                  type="text"
                  placeholder="e.g. BTC Momentum Scanner"
                  className="bg-black/50 border-slate-700 text-slate-200"
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Allocation %</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  placeholder="1.0"
                  className="bg-black/50 border-slate-700 text-slate-200 font-mono"
                  value={newProfileAllocation}
                  onChange={(e) => setNewProfileAllocation(e.target.value)}
                />
                <p className="text-[10px] text-slate-600 mt-1">Percentage of portfolio allocated to this agent.</p>
              </div>
              <div className="bg-black/30 border border-slate-800 rounded-lg p-3">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-1">Strategy Template</p>
                <p className="text-xs text-slate-400">A default momentum strategy will be applied. You can edit the JSON rules after creation.</p>
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-800">
              <Button variant="ghost" onClick={() => setShowCreateModal(false)} className="text-slate-400">
                Cancel
              </Button>
              <Button
                onClick={handleCreateProfile}
                disabled={isCreating || !newProfileName.trim()}
                className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold"
              >
                {isCreating ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> CREATING...</>
                ) : (
                  <><Plus className="w-4 h-4 mr-2" /> CREATE PROFILE</>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && selectedProfile && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-red-500/30 rounded-xl shadow-2xl w-full max-w-sm mx-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-5 text-center">
              <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
                <Trash2 className="w-6 h-6 text-red-400" />
              </div>
              <h2 className="text-lg font-bold text-white mb-2">Delete Profile?</h2>
              <p className="text-sm text-slate-400">
                This will permanently deactivate <strong className="text-white">{selectedProfile.name || selectedProfile.profile_id}</strong>. This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3 px-6 py-4 border-t border-slate-800">
              <Button variant="ghost" onClick={() => setShowDeleteConfirm(false)} className="flex-1 text-slate-400">
                Cancel
              </Button>
              <Button
                onClick={handleDeleteProfile}
                disabled={isDeleting}
                className="flex-1 bg-red-600 hover:bg-red-500 text-white font-bold"
              >
                {isDeleting ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> DELETING...</>
                ) : (
                  "DELETE"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

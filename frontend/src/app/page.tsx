"use client";

import { DetectControls, DetectResults } from "../components/DetectPanel";
import { DocumentHeader } from "../components/DocumentHeader";
import { EmptyState } from "../components/EmptyState";
import { Header } from "../components/Header";
import { HumanizeControls, HumanizeResults } from "../components/HumanizePanel";
import { LoadingPane } from "../components/LoadingPane";
import { RevisionTimeline } from "../components/RevisionTimeline";
import { Sidebar } from "../components/Sidebar";
import { TabSwitcher } from "../components/TabSwitcher";
import { TiptapEditor } from "../components/TiptapEditor";
import { useAppStore } from "../store/app";

export default function Home() {
  const { activeTab } = useAppStore();

  return (
    <div className="flex flex-col min-h-screen">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto w-full px-6 py-6">
            <DocumentHeader />

            <div className="mt-4">
              <TabSwitcher />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Input / Controls */}
              <div className="space-y-4">
                <TiptapEditor />
                {activeTab === "detect" ? <DetectControls /> : <HumanizeControls />}
                <RevisionTimeline />
              </div>

              {/* Results */}
              <div className="space-y-4">
                <LoadingPane />
                {activeTab === "detect" ? <DetectResults /> : <HumanizeResults />}
                <EmptyState />
              </div>
            </div>
          </div>
        </main>
      </div>

      <footer className="border-t border-zinc-800 px-6 py-2">
        <p className="text-center text-xs text-zinc-600">
          Runs 100% locally · Tiptap/ProseMirror editor · RoBERTa + Qwen 3.5-4B
          detection · Ollama (qwen3.5:9b) rewriting · SHA-256 provenance chain
        </p>
      </footer>
    </div>
  );
}

"use client";

import { DetectControls, DetectResults } from "../components/DetectPanel";
import { EmptyState } from "../components/EmptyState";
import { Header } from "../components/Header";
import { HumanizeControls, HumanizeResults } from "../components/HumanizePanel";
import { LoadingPane } from "../components/LoadingPane";
import { TabSwitcher } from "../components/TabSwitcher";
import { TextInput } from "../components/TextInput";
import { useAppStore } from "../store/app";

export default function Home() {
  const { activeTab } = useAppStore();

  return (
    <div className="flex flex-col min-h-screen">
      <Header />

      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        <TabSwitcher />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input / Controls */}
          <div className="space-y-4">
            <TextInput />
            {activeTab === "detect" ? <DetectControls /> : <HumanizeControls />}
          </div>

          {/* Results */}
          <div className="space-y-4">
            <LoadingPane />
            {activeTab === "detect" ? <DetectResults /> : <HumanizeResults />}
            <EmptyState />
          </div>
        </div>
      </main>

      <footer className="border-t border-zinc-800 px-6 py-3">
        <p className="text-center text-xs text-zinc-600">
          Runs 100% locally · RoBERTa + Qwen 3.5 detection · Sentence-level adversarial
          humanization · Ollama LLM rewriting
        </p>
      </footer>
    </div>
  );
}

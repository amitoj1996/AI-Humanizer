"use client";

import { useEffect } from "react";

import { api } from "../lib/api";
import { useAppStore } from "../store/app";

export function ModelSelector() {
  const { models, selectedModel, ollamaAvailable, setModels, setSelectedModel, setOllamaAvailable } =
    useAppStore();

  useEffect(() => {
    api
      .listModels()
      .then((d) => {
        setOllamaAvailable(d.ollama_available);
        setModels(d.models ?? []);
        if ((d.models ?? []).length) setSelectedModel(d.models[0]);
      })
      .catch(() => setOllamaAvailable(false));
  }, [setModels, setOllamaAvailable, setSelectedModel]);

  const handleChange = async (model: string) => {
    setSelectedModel(model);
    await api.selectModel(model).catch(() => {});
  };

  return (
    <div className="flex items-center gap-3">
      {ollamaAvailable === false && (
        <span className="text-xs text-red-400 bg-red-400/10 px-2 py-1 rounded">
          Ollama offline
        </span>
      )}
      {models.length > 0 && (
        <select
          value={selectedModel}
          onChange={(e) => handleChange(e.target.value)}
          className="text-sm bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300"
        >
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, BenchmarkConfig } from "@/lib/api";

type PresetType = "quick" | "standard" | "stress";

const PRESETS = {
  quick: {
    concurrency: [1, 5, 10],
    num_prompts: 50,
    input_len: 128,
    output_len: 64,
    description: "Fast validation test",
  },
  standard: {
    concurrency: [1, 10, 50, 100],
    num_prompts: 200,
    input_len: 256,
    output_len: 128,
    description: "Balanced performance test",
  },
  stress: {
    concurrency: [10, 50, 100, 200, 500],
    num_prompts: 500,
    input_len: 512,
    output_len: 256,
    description: "High load stress test",
  },
};

export default function NewBenchmarkPage() {
  const router = useRouter();
  const [config, setConfig] = useState<Partial<BenchmarkConfig>>({
    server_url: "http://host.docker.internal:8000",
    model: "",
    adapter: "openai",
    concurrency: [1, 10, 50],
    num_prompts: 100,
    input_len: 256,
    output_len: 128,
    stream: true,
    warmup: 3,
    timeout: 120,
  });

  const [goodputEnabled, setGoodputEnabled] = useState(false);
  const [goodput, setGoodput] = useState({ ttft: 500, tpot: 100, e2e: 10000 });
  const [selectedPreset, setSelectedPreset] = useState<PresetType | null>(null);

  const applyPreset = (preset: PresetType) => {
    const presetConfig = PRESETS[preset];
    setConfig({
      ...config,
      concurrency: presetConfig.concurrency,
      num_prompts: presetConfig.num_prompts,
      input_len: presetConfig.input_len,
      output_len: presetConfig.output_len,
    });
    setSelectedPreset(preset);
  };

  const mutation = useMutation({
    mutationFn: (config: BenchmarkConfig) => api.startBenchmark(config),
    onSuccess: (data) => {
      router.push(`/benchmark/${data.run_id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const finalConfig: BenchmarkConfig = {
      server_url: config.server_url!,
      model: config.model!,
      adapter: config.adapter!,
      concurrency: config.concurrency!,
      num_prompts: config.num_prompts!,
      input_len: config.input_len!,
      output_len: config.output_len!,
      stream: config.stream!,
      warmup: config.warmup!,
      timeout: config.timeout!,
      api_key: config.api_key,
    };

    if (goodputEnabled) {
      finalConfig.goodput_thresholds = {
        ttft_ms: goodput.ttft,
        tpot_ms: goodput.tpot,
        e2e_ms: goodput.e2e,
      };
    }

    mutation.mutate(finalConfig);
  };

  return (
    <div className="w-full">
      {/* Header with buttons */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          New Benchmark
        </h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={mutation.isPending || !config.model}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {mutation.isPending ? "Starting..." : "Start Benchmark"}
          </button>
        </div>
      </div>

      {mutation.error && (
        <p className="text-red-500 text-sm mb-3">
          Error: {(mutation.error as Error).message}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Section Header: Test Configuration */}
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Test Configuration
          </h2>
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
        </div>

        {/* Main Grid: Presets | Server + Load Parameters */}
        <div className="grid grid-cols-3 gap-4">
          {/* Presets Panel */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex flex-col">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
              Presets
            </h3>
            <div className="flex flex-col gap-2 mb-4">
              {(Object.keys(PRESETS) as PresetType[]).map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all text-left ${
                    selectedPreset === preset
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                  }`}
                >
                  {preset.charAt(0).toUpperCase() + preset.slice(1)}
                  <span className={`block text-xs mt-0.5 ${
                    selectedPreset === preset ? "text-blue-100" : "text-gray-500"
                  }`}>
                    {PRESETS[preset].description}
                  </span>
                </button>
              ))}
            </div>

            {/* Preset Preview */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3 flex-1">
              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                {selectedPreset ? "Selected Settings" : "Current Settings"}
              </h4>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Concurrency</span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {config.concurrency?.join(", ")}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Prompts</span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {config.num_prompts}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Input Length</span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {config.input_len} tokens
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Output Length</span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {config.output_len} tokens
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Server Settings + Load Parameters */}
          <div className="col-span-2 flex flex-col gap-4">
            {/* Server Settings */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                Server Settings
              </h3>
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                ML35: vLLM (Local Serving)
              </div>
              <div className="space-y-2">
                <input
                  type="text"
                  value={config.server_url}
                  onChange={(e) =>
                    setConfig({ ...config, server_url: e.target.value })
                  }
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="http://host.docker.internal:8000"
                  required
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={config.model}
                    onChange={(e) => setConfig({ ...config, model: e.target.value })}
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Model (e.g., qwen3-14b)"
                    required
                  />
                  <input
                    type="password"
                    value={config.api_key ?? ""}
                    onChange={(e) =>
                      setConfig({ ...config, api_key: e.target.value || undefined })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="API Key (optional)"
                  />
                </div>
              </div>
            </div>

            {/* Load Parameters */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex-1">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                Load Parameters
              </h3>
              <div className="grid grid-cols-4 gap-3 mb-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    Concurrency
                  </label>
                  <input
                    type="text"
                    value={config.concurrency?.join(",")}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        concurrency: e.target.value.split(",").map(Number),
                      })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="1,10,50"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    Prompts
                  </label>
                  <input
                    type="number"
                    value={config.num_prompts}
                    onChange={(e) =>
                      setConfig({ ...config, num_prompts: Number(e.target.value) })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    Input Len
                  </label>
                  <input
                    type="number"
                    value={config.input_len}
                    onChange={(e) =>
                      setConfig({ ...config, input_len: Number(e.target.value) })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="256"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    Output Len
                  </label>
                  <input
                    type="number"
                    value={config.output_len}
                    onChange={(e) =>
                      setConfig({ ...config, output_len: Number(e.target.value) })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="128"
                  />
                </div>
              </div>

              {/* Streaming Option */}
              <label className="flex items-center gap-2 cursor-pointer mb-4">
                <input
                  type="checkbox"
                  checked={config.stream}
                  onChange={(e) =>
                    setConfig({ ...config, stream: e.target.checked })
                  }
                  className="w-4 h-4 rounded border-gray-300"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Streaming Mode
                </span>
              </label>

              {/* Load Parameters 설명 */}
              <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <div><strong>Concurrency</strong>: 동시 요청 수 (쉼표로 구분)</div>
                  <div><strong>Prompts</strong>: 각 레벨당 총 요청 수</div>
                  <div><strong>Input Len</strong>: 입력 프롬프트 토큰 수</div>
                  <div><strong>Output Len</strong>: 생성할 최대 토큰 수</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Goodput SLO Section */}
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Goodput SLO
          </h2>
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
          <span className="text-xs text-gray-500 dark:text-gray-400">선택사항</span>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-start gap-6 mb-4">
            {/* Enable Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={goodputEnabled}
                onChange={(e) => setGoodputEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                SLO 추적 활성화
              </span>
            </label>

            {/* SLO Inputs */}
            <div className={`flex items-center gap-4 ${!goodputEnabled && "opacity-50 pointer-events-none"}`}>
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  TTFT
                </label>
                <input
                  type="number"
                  value={goodput.ttft}
                  onChange={(e) =>
                    setGoodput({ ...goodput, ttft: Number(e.target.value) })
                  }
                  className="w-20 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center"
                />
                <span className="text-xs text-gray-400">ms</span>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  TPOT
                </label>
                <input
                  type="number"
                  value={goodput.tpot}
                  onChange={(e) =>
                    setGoodput({ ...goodput, tpot: Number(e.target.value) })
                  }
                  className="w-20 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center"
                />
                <span className="text-xs text-gray-400">ms</span>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  E2E
                </label>
                <input
                  type="number"
                  value={goodput.e2e}
                  onChange={(e) =>
                    setGoodput({ ...goodput, e2e: Number(e.target.value) })
                  }
                  className="w-24 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center"
                />
                <span className="text-xs text-gray-400">ms</span>
              </div>
            </div>
          </div>

          {/* Help Text - 항상 표시 */}
          <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
            <div className="font-medium text-gray-700 dark:text-gray-300 mb-2">
              SLO 임계값 설명 (모든 조건을 만족하는 요청만 "Good"으로 집계)
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              <div className="flex items-start gap-2">
                <span className="font-semibold text-blue-600 dark:text-blue-400 min-w-[40px]">TTFT</span>
                <span>첫 번째 토큰까지의 시간 (Time To First Token) - 사용자가 응답 시작을 체감하는 대기 시간</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="font-semibold text-green-600 dark:text-green-400 min-w-[40px]">TPOT</span>
                <span>토큰당 출력 시간 (Time Per Output Token) - 각 글자가 생성되는 속도</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="font-semibold text-orange-600 dark:text-orange-400 min-w-[40px]">E2E</span>
                <span>전체 응답 시간 (End-to-End) - 요청부터 응답 완료까지 총 소요 시간</span>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 text-gray-400">
              예: 통화 AI 상담 시스템에서 1초 내 응답 목표 시 TTFT=500ms, TPOT=100ms, E2E=10000ms 권장
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

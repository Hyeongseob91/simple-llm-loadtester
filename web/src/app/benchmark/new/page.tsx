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
    description: "Quick test - Fast validation",
  },
  standard: {
    concurrency: [1, 10, 50, 100],
    num_prompts: 200,
    input_len: 256,
    output_len: 128,
    description: "Standard test - Balanced benchmark",
  },
  stress: {
    concurrency: [10, 50, 100, 200, 500],
    num_prompts: 500,
    input_len: 512,
    output_len: 256,
    description: "Stress test - Heavy load testing",
  },
};

export default function NewBenchmarkPage() {
  const router = useRouter();
  const [config, setConfig] = useState<Partial<BenchmarkConfig>>({
    server_url: "http://localhost:8000",
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
  const [goodput, setGoodput] = useState({ ttft: 500, tpot: 50, e2e: 3000 });
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
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
        New Benchmark
      </h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Test Presets */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Quick Presets
          </h2>
          <div className="grid grid-cols-3 gap-4">
            {(Object.keys(PRESETS) as PresetType[]).map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => applyPreset(preset)}
                className={`p-4 rounded-lg border-2 transition-all ${
                  selectedPreset === preset
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30"
                    : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
                }`}
              >
                <div className="font-semibold text-gray-900 dark:text-white capitalize mb-1">
                  {preset}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {PRESETS[preset].description}
                </div>
                <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                  <div>Concurrency: {PRESETS[preset].concurrency.join(", ")}</div>
                  <div>Prompts: {PRESETS[preset].num_prompts}</div>
                  <div>
                    Tokens: {PRESETS[preset].input_len}/{PRESETS[preset].output_len}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Server Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Server Settings
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Server URL
              </label>
              <input
                type="text"
                value={config.server_url}
                onChange={(e) =>
                  setConfig({ ...config, server_url: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="http://localhost:8000"
                required
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                OpenAI-compatible API 서버 주소 (vLLM, SGLang, Ollama 등)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Model Name
              </label>
              <input
                type="text"
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="qwen3-14b"
                required
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                vLLM --served-model-name 또는 모델 ID
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                API Key (optional)
              </label>
              <input
                type="password"
                value={config.api_key ?? ""}
                onChange={(e) =>
                  setConfig({ ...config, api_key: e.target.value || undefined })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="sk-..."
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                인증이 필요한 서버용 (vLLM 기본 설정은 불필요)
              </p>
            </div>
          </div>
        </div>

        {/* Test Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Test Settings
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Concurrency Levels
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="1,10,50,100"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                동시 요청 수 (예: 1,5,10 → 각 레벨별로 테스트 실행)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Number of Prompts
              </label>
              <input
                type="number"
                value={config.num_prompts}
                onChange={(e) =>
                  setConfig({ ...config, num_prompts: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                각 동시성 레벨당 보낼 총 요청 수
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Input Length
              </label>
              <input
                type="number"
                value={config.input_len}
                onChange={(e) =>
                  setConfig({ ...config, input_len: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                입력 프롬프트 토큰 수 (대략적)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Output Length
              </label>
              <input
                type="number"
                value={config.output_len}
                onChange={(e) =>
                  setConfig({ ...config, output_len: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                생성할 최대 출력 토큰 수 (max_tokens)
              </p>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={config.stream}
                onChange={(e) =>
                  setConfig({ ...config, stream: e.target.checked })
                }
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Enable Streaming
              </span>
            </label>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              (체크 시 TTFT, ITL 측정 가능. 해제 시 전체 응답 한번에 수신)
            </span>
          </div>
        </div>

        {/* Goodput Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Goodput SLO Thresholds
            </h2>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={goodputEnabled}
                onChange={(e) => setGoodputEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Enable
              </span>
            </label>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
            SLO 임계값을 모두 만족하는 요청의 비율(%)을 측정합니다. NVIDIA GenAI-Perf 기반 품질 지표.
          </p>

          {goodputEnabled && (
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  TTFT (ms)
                </label>
                <input
                  type="number"
                  value={goodput.ttft}
                  onChange={(e) =>
                    setGoodput({ ...goodput, ttft: Number(e.target.value) })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Time To First Token - 첫 토큰까지 시간
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  TPOT (ms)
                </label>
                <input
                  type="number"
                  value={goodput.tpot}
                  onChange={(e) =>
                    setGoodput({ ...goodput, tpot: Number(e.target.value) })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Time Per Output Token - 토큰당 생성 시간
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  E2E (ms)
                </label>
                <input
                  type="number"
                  value={goodput.e2e}
                  onChange={(e) =>
                    setGoodput({ ...goodput, e2e: Number(e.target.value) })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  End-to-End Latency - 전체 응답 시간
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {mutation.isPending ? "Starting..." : "Start Benchmark"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-6 py-2 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 font-medium"
          >
            Cancel
          </button>
        </div>

        {mutation.error && (
          <p className="text-red-500 text-sm">
            Error: {(mutation.error as Error).message}
          </p>
        )}
      </form>
    </div>
  );
}
